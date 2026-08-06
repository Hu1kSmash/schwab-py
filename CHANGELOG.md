# Changelog

This is a maintained fork of [`alexgolec/schwab-py`](https://github.com/alexgolec/schwab-py).
Versions below 1.6.0 are upstream releases; see the upstream repository for their notes.

Every change in this fork has also been offered upstream as a pull request. Where upstream merges
one, the fork's divergence shrinks accordingly.

---

## 1.7.2

### Fixed

**Cancelling a stream request left the client unusable.** A request waiting for
its response races two things: the response arriving via whoever is currently
reading the socket, and the socket becoming free so it can read for itself. The
second is an `asyncio.Lock.acquire()`, and it can succeed at the same moment the
waiter stops waiting.

That race was handled when the wait timed out, but not when the waiting
coroutine was cancelled. A cancellation delivered while the acquire had already
completed skipped the branch which releases, so the read lock was left held by
nobody:

    after cancel: read_lock held=True, request_lock held=False
    client still usable after a cancelled request: no

Nothing could read after that, for the rest of the process. Every exit from the
wait now releases what it took.

This was introduced in 1.7.0 by the change which stopped requests blocking
behind a waiting consumer, so it does not affect 1.6.0 or earlier. Anyone on
1.7.0 or 1.7.1 who cancels stream operations -- during shutdown, or by wrapping
a subscription in a timeout -- should take this.

---

## 1.7.1

No library changes: `schwab/` is identical to 1.7.0 apart from the version string.
This release exists because the 1.7.0 tag shipped install instructions which
installed the wrong project.

### Fixed

**The install instructions installed upstream.** The README's getting-started
section and `docs/getting-started.rst` both said `pip install schwab-py`, which
fetches the original project from PyPI. A reader who got as far as installing
got upstream, whatever the fork notice at the top of the page said -- and it
would appear to work, since the importable package has the same name either way.
The fork notice itself still pinned 1.6.0.

**The documentation build could not run from a clean checkout.**
`docs/requirements.txt` pinned `websockets==12.0`, and this library imports
`websockets.asyncio`, which does not exist before 14.0. It went unnoticed because
a development environment already has a current websockets, so it only failed
somewhere clean. `authlib` and `httpx` were pinned below the floors `setup.py`
requires. All are floors now, so they cannot drift from `setup.py` silently.

### Added

A security policy, an issue template chooser, a pull request template, and
`.gitignore` rules for the token file -- which is a live credential, and which
nothing previously stopped git from offering to commit.

---

## 1.7.0

### Fixed

**Response redaction never ran.** Both client modules imported
`register_redactions_from_response` and then defined a no-op of the same name
over the top of it, so every call after every request went to the stub. The API
key and the token are registered elsewhere and were genuinely redacted, but
nothing the redactor was meant to pick out of responses — account numbers,
account hashes, the other id-ish values it looks for — ever was. Since
`enable_bug_report_logging()` tells users their logs are scrubbed, someone
following the documented process for filing a bug could publish those.

Collection is now gated on `enable_bug_report_logging()`, which is the only
thing that promises redaction and already documents that it carries a
performance penalty. Clients which do not call it are unaffected, which is what
they were getting anyway.

**A request could not be made while a consumer was waiting for a message.** One
lock covered every stream operation and `handle_message` held it across the
read, so on a quiet stream a subscription, unsubscription or logout waited for
a message to arrive first — indefinitely, if none did. Measured beforehand: a
subscribe issued against a parked consumer sat for a full second without a
single byte reaching the socket.

Reading and requesting are now separated. A read lock keeps a single reader,
since `websockets` does not allow two coroutines to call `recv()` concurrently,
and whoever holds it routes what it reads: a response to a request in flight is
delivered to the coroutine waiting for it. A request sends immediately and then
waits on whichever comes first — its response arriving via the reader, or the
socket becoming free so it can read itself. Response validation and every error
it can raise are unchanged.

**The price history helpers ignored the date range they were given.**
`get_price_history` documents that `period` "should not be provided if
`start_datetime` and `end_datetime`", and all seven `get_price_history_every_*`
helpers provided both. `period` is now sent only when no range was asked for,
since the helpers synthesize one spanning decades when the caller gives none.

What Schwab does when it receives both is **not** consistent across accounts. The
upstream report describes the range being disregarded; a funded margin account we
had measurements from returned byte-identical responses with and without `period`
across four frequency and range combinations, so there the range was honoured
either way. Both can be true — entitlements, symbol class, or the API changing
since the report would all explain it. The fix does not depend on which: sending a
`period` the caller never asked for is wrong regardless, and it is what the
library's own docstring says not to do.

**The asyncio example called a function which does not exist.**
`asyncio.run_until_complete()` is not a thing; `run_until_complete` is a method
on an event loop. The example now uses `asyncio.run()`.

**Two format strings did nothing.** A DELETE was logged with
`'Req %s: DELETE to %s'.format(...)`, which does not substitute `%s`, so every
DELETE logged its placeholders verbatim. The price history path called
`.format(symbol)` on a string with no placeholders.

### Added

**`OrderBuilder.set_price_offset`.** The stop-price side already had a basis, a
type and an offset; the price-linked side had a basis and a type but no offset,
so a price-linked order could not be expressed at all and had to be assembled as
a raw order.

### Changed

Removed the original project's Discord invitations, funding links and badges,
its `tda-api` transition guide, and 44 links to `developer.tdameritrade.com` and
`tickertape.tdameritrade.com`, whose portals were retired along with the API
they documented. Several documentation and issue links pointed at repositories
which do not exist. Documentation now describes this fork's behaviour, and
issues are directed at this fork's tracker with a note that anything not caused
by these changes is better reported upstream.

`tox.ini` now covers py313 and py314, which CI already ran.

### Breaking changes

- A request which is never answered raises `ResponseTimeoutError` rather than
  blocking message handling. This was already true in 1.6.0; what changed here
  is that it no longer blocks anything except subsequent requests.
- Messages read while a request is in flight are handed to `handle_message` in
  arrival order. Previously they were held back until the request completed,
  which could not interleave because the lock prevented it.

### Verification

Full suite passes on CPython 3.12 and 3.14.

---

## 1.6.0

First release of the fork, branching from upstream 1.6.0's predecessor, 1.5.1.

### Fixed

**Prices passed as floats could be a cent too low.** `set_price` and `set_stop_price` truncate
rather than round, which is intentional and documented, but the truncation was computed by scaling a
binary float and taking `int()`. That truncates the representation error along with the value:
`8.2 * 100` is `819.9999999999999`, so a price already at two decimal places came back as `8.19`.
Across every cent from $1.00 to $1000.00, 4,583 of 99,901 prices — 4.6% — were affected, always one
tick low and always silently. Truncation is now done in decimal. Sub-dollar prices at four decimal
places were wrong 5.7% of the time and are likewise fixed.

**The token file could be destroyed by a crash during a refresh.** The token was written with a
plain truncating `open(path, 'w')`, so a process that died between the truncation and the end of the
write left a file that could not be parsed — unrecoverable without a fresh interactive login. Tokens
are now written to a temporary file and renamed into place, which is atomic, so an interrupted write
leaves the existing token intact. The rename is flushed, and symlinked token paths are resolved so a
linked token file is written through rather than replaced.

**The token file was created world-readable.** It was written with whatever the umask permitted,
commonly `0644`, despite holding a credential granting full account access. It is now created `0600`,
with the mode set before the file becomes visible at its final name. Tokens written by earlier
versions are corrected on their next refresh.

**A stream handler that raised could take down the receive loop, or fail silently.** Handlers are
registered through one API but were dispatched with opposite error semantics: a synchronous handler
that raised propagated out of `handle_message`, aborting dispatch for every other handler on that
message and surfacing in the caller's loop as though the connection had failed; an asynchronous one
was scheduled and never awaited, so its exception was discarded entirely. Both kinds are now
isolated and logged. Message relabeling is inside the guard, so a message with an unexpected shape
is reported rather than escaping.

**A request the streaming server never answered wedged the entire client.** `_await_response` waited
with no upper bound while holding the lock that serializes stream operations, so an unanswered
request blocked every other operation — including message handling — for the life of the process.
Requests now time out. The websockets keepalive does not cover this case: a connection that is alive
but not answering keeps replying to pings.

**`notify` messages without a `service` key raised.** The `notify` dispatch path lacked the
membership check its `data` counterpart has. With a `defaultdict` this silently accreted an empty
entry per unrecognised service, and a frame without a `service` key raised `KeyError` out of
`handle_message`.

**The default price-history end date was off by the host's UTC offset**, and used the deprecated
`datetime.utcnow()`. `utcnow()` returns a naive datetime holding a UTC wall time, which
`_format_date_as_millis` then converted as though it were local.

**`get_orders_for_account` documented a `statuses` parameter that does not exist.** Passing it
raised `TypeError`. Multiple statuses are deliberately rejected, so the line was vestigial. Both
order-query methods now state that only a single status is accepted.

### Added

**`StreamClient.close()`**, plus `async with` support. There was previously no way to close a
stream: `logout()` sent the logout frame but left the socket, its keepalive task and its buffers
alive until the object was collected, leaving callers to finalize the connection during interpreter
shutdown. `logout()` now closes the socket as well, and a failure to close no longer masks the error
that caused it.

**Twenty-four equity order templates**, covering stop, stop-limit, trailing stop, trailing stop
limit, market-on-close and limit-on-close across all four equity instructions. The existing eight
templates covered `MARKET` and `LIMIT` only, so every other order type had to be assembled by hand.
Signatures of the existing templates are unchanged.

On the trailing templates, `stop_price_link_type` is a required argument rather than a defaulted
one. An offset of `2.5` means a 2.5% trail under `PERCENT` and a $2.50 trail under `VALUE`, the
venue accepts both, and there is no error to observe if the wrong one is chosen — so the caller is
asked to say which they mean.

**`response_timeout`** on `StreamClient`, defaulting to 60 seconds. `None` restores the previous
wait-forever behaviour.

### Changed

**`StreamClient` now uses `websockets.asyncio` instead of `websockets.legacy`.** The legacy
implementation has been deprecated since websockets 14.0 (2024-11-09), and because the import is at
module scope its eventual removal would break `import schwab.streaming` outright rather than
degrading a single code path. The dependency floor is now `websockets>=14.0`.

`websocket_connect_args` is a documented passthrough to `connect()`, and websockets 14.0 renamed
`extra_headers` to `additional_headers` and removed `create_protocol` and `read_limit`.
`extra_headers` is translated automatically with a `DeprecationWarning`; the removed arguments raise
an error naming the problem rather than an opaque `TypeError` from inside the library.

The connection object is now `ClientConnection` rather than `WebSocketClientProtocol`. Nothing in
the library names or annotates it, but code that annotates it itself will need updating.

**`Duration` now documents which values Schwab accepts for equity orders.** `IMMEDIATE_OR_CANCEL`,
`END_OF_WEEK`, `END_OF_MONTH` and `NEXT_END_OF_MONTH` are rejected at placement for equities with
`HTTP 400`. The values are retained, since they may be valid for other asset types, and because
removing an enum member would break anyone who has one wired up. Established by placing one equity
order per value against a live account.

### Breaking changes

- A synchronous stream handler that raises no longer propagates to the caller. Failures are logged
  with the service name. Callers relying on an exception to detect handler bugs should watch the
  `schwab.streaming` logger instead.
- Stream operations now raise `ResponseTimeoutError` after 60 seconds rather than waiting forever.
  Pass `response_timeout=None` to restore the old behaviour.
- `websockets>=14.0` is required.

### Verification

The full test suite passes on CPython 3.12 and 3.14. The websockets migration was additionally
verified against a live Schwab stream: login, level-one and account-activity subscriptions, a custom
`ssl_context`, and the `extra_headers` compatibility path.

The behaviour of `Duration` and the required fields for each equity order type were established by
placing real orders against a live account rather than from documentation.
