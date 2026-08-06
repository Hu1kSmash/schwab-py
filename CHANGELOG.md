# Changelog

This is a maintained fork of [`alexgolec/schwab-py`](https://github.com/alexgolec/schwab-py).
Versions below 1.6.0 are upstream releases; see the upstream repository for their notes.

Every change in this fork has also been offered upstream as a pull request. Where upstream merges
one, the fork's divergence shrinks accordingly.

---

## 1.9.0

From a production-readiness audit which mostly ran the library rather than
reading it. Four defects, three of them silent.

Two change behaviour in ways worth reading before upgrading: aware datetimes
now produce different (correct) requests on three endpoints, and a NaN price is
now refused rather than sent.

### Fixed

**A timezone-aware datetime was formatted, not converted, before being labelled
UTC.** Schwab documents `fromEnteredTime`, `toEnteredTime` and the transaction
dates as `yyyy-MM-dd'T'HH:mm:ss.SSSZ`, where the trailing `Z` asserts UTC.
`_format_date_as_iso` applied `strftime` to whatever it was given, so a
datetime carrying any other timezone had its local wall clock stamped as UTC:

```python
eastern.localize(datetime.datetime(2024, 6, 5, 0, 3, 2))   # == 04:03:02 UTC
# sent as fromEnteredTime=2024-06-05T00:03:02Z             -- four hours early
```

Passing a correctly-zoned datetime is what triggered it. Naive datetimes were
unaffected, as were the price history endpoints, which use a different encoding
that was already correct. Affects `get_orders_for_account`,
`get_orders_for_all_linked_accounts` and `get_transactions`. Offered upstream
as #258.

**A response nobody was waiting for ended the caller's receive loop.**
`handle_message` raised `UnexpectedResponse` on any response frame. One reaches
it whenever a request was abandoned -- timed out, or cancelled -- and the
server answered afterwards, and that answer is frequently a *successful* one.
So a subscribe which timed out client-side and in fact worked killed the
session the moment Schwab acknowledged it, taking every message queued behind
it. That is most likely exactly when the venue is slow, which is when a stream
is least worth dropping. Now logged and skipped. `UnexpectedResponse` still
covers a response whose service, command or request id does not match the
request being waited on. Offered upstream as #261.

**Prices which are not a finite number built sendable orders.**

```python
equity_buy_limit('AAPL', 10, float('nan')).build()
# {'orderType': 'LIMIT', 'price': 'NaN', ...}
```

NaN is not typed, it is computed -- a limit derived from a quote that was
missing. The builder already refused a non-positive quantity, so this is the
same check on the other half of the order. The string spellings are refused
too, since `str()` of a computed price is the documented way to pass one.
Strings which are not numbers at all still pass through, and `copy_price` still
bypasses everything as documented. Offered upstream as #262.

**Bug report logs did not redact Schwab's account identifiers.** The default
patterns matched an earlier API's field names -- `accountId`, `displayName`.
Schwab returns `accountNumber` and `hashValue` and neither matched anything, so
the two identifiers a user is least likely to want in a public issue were the
two that survived. Named in full rather than adding `account` as a substring:
redaction is a whole-log string replacement, and `account` also matches
`accountValue` and `accountColor`, which would take every balance and the word
"Green" with it. Offered upstream as #260.

### Added

**A warning when a date parameter is given a datetime with no timezone.** These
parameters name an instant; a naive datetime does not. The epoch-millisecond
encoding reads one as the host's local time, so the same source line sends
different requests on different machines:

```
host set to UTC:                startDate=1786008600000
host set to America/New_York:   startDate=1786023000000
```

Four hours apart, with nothing in the request recording which was meant.
Warning rather than reinterpreting: silently treating them as UTC would change
behaviour for anyone relying on local time without telling them. Aware
datetimes and plain `date` objects are unaffected. Offered upstream as #259.

### Documentation

A **Dates and Times** section in the client documentation, which previously
said nothing about timezones anywhere. Covers both encodings, the measured
numbers above, and the three spellings that remove the ambiguity.

### Notes

Nothing here changes how a request is built for a caller already passing aware
datetimes to the price history endpoints, or already passing prices as strings.

The audit also confirmed, by measurement rather than reading: 80 `SIGKILL`s
inside the token write window corrupted nothing; 400 streaming cancellation
storms left no orphaned lock and every client usable, where v1.7.1 fails 40 out
of 40; price truncation agrees exactly with an independent oracle across 40,009
values; and all 48 order templates round-trip byte-identically through
`contrib.orders`.

## 1.8.1

### Fixed

**`enable_bug_report_logging()` wrote its report to whatever `sys.stderr` was at
import time.** The stream was captured as a default argument, which Python
evaluates once when the module is imported -- not when the logs are written,
which happens at program exit. An application that redirects `sys.stderr` after
importing the library, as a daemon writing to a log file does, had its bug
report delivered to the stream it redirected away from. Measured with a
`StringIO` standing in for the log file, the redirected stream received 0 bytes
before the fix and the whole report after it.

If that original stream had since been closed, the program's last output was a
traceback out of an `atexit` handler instead of the report. This library's own
test suite printed one on every run.

`sys.stderr` is now looked up when the report is written, and a closed stream is
treated as nowhere to write rather than something to raise about. Passing
`output=` explicitly is unchanged. Offered upstream as #257.

### Documentation

The README's "Why should I use `schwab-py`?" section listed two reasons and left
out the two largest parts of the library: the streaming client and order
construction. Rewritten to cover both, with the "minimal wrapping" claim narrowed
to the HTTP layer where it holds -- the parameter enums, `OrderBuilder` and the
streaming relabeler are all deliberately opinionated. Offered upstream as #255.

Nothing in this release changes how a request is built or an order is
constructed.

## 1.8.0

Most of this comes from reading Schwab's published documentation against the
library, rather than from finding something at runtime.

### Fixed

**Field 20 of `LEVELONE_OPTIONS` is the strike price, not a "strike type".**
Schwab's streamer documentation gives it as `| 20 | Strike Price | double |
Contract strike price |`. It was named `STRIKE_TYPE`, so every relabeled option
quote carried a key describing neither the field nor its contents -- and the
enum had no strike price at all, across fifty-six fields on an options quote
feed. Reported upstream as #197.

`STRIKE_TYPE` is kept as an alias, so code naming it keeps working. Messages are
now labeled `STRIKE_PRICE`, which is a **breaking change** for anything reading
that key.

This needed a supporting fix. `key_mapping` built its number-to-name table from
`__members__`, which yields aliases as well as canonical members, so whichever
alias was defined last would silently have decided the label. It now iterates
the enum itself. No other field enum has an alias, so nothing else changes.

**A historical order with an `UNKNOWN` field could not be reconstructed, and
said so badly.** Schwab documents `UNKNOWN` as a value both `duration` and
`orderType` can come back as, while stating it is not accepted as an input.
Omitting it from the request enums is therefore right, but
`construct_repeat_order` fed historical values into those same enums and failed
with a bare `KeyError: 'UNKNOWN'`, naming neither the field nor the problem.

Such an order genuinely cannot be repeated, so the fix is to say so rather than
to accept the value: `UnrepeatableOrderError` names the field, carries the
value, and explains that Schwab reports it but will not accept it.

**`get_price_history`'s docstring contradicted Schwab's documentation.** It said
`period` "should not be provided" alongside a date range. What Schwab documents,
under `startDate`, is "if not specified startDate will be (endDate - period)" --
so `period` derives a start date when one is absent rather than overriding one
that is present. Supplying both is harmless. The valid `period` values per
`period_type` are now documented too; they were not stated anywhere.

That wording is what led 1.7.0's release notes to claim Schwab honours `period`
over an explicit range. It does not, and those notes have been corrected.

### Added

`UnrepeatableOrderError`, described above.

### Changed

Documented what this fork already did but never explained: that the token file is
a credential written `0600` and replaced atomically, that surrounding whitespace
is stripped from keys and secrets and why the warning is worth acting on, and
that a subscription can be made while another coroutine waits in
`handle_message`.

CI now runs `actions/checkout` and `actions/setup-python` at v7 rather than v2,
which were five years old and being force-run on a Node runtime they were not
built for. Dependabot watches them monthly so they cannot drift that far again.

### Verified against the documentation, and correct

Worth recording, since the point of the exercise was to find gaps: all thirteen
order enums match the published schemas value for value, apart from the `UNKNOWN`
handling above. All eleven market-data parameter enums match. Every market-data
endpoint and parameter is implemented. Across eight streaming services and 230
fields, every field number is correct and field 20 was the only name that meant
something different from the field.

One thing that looked wrong and is not: the `CHART_EQUITY` field table in
Schwab's streamer documentation disagrees with this library, and the library is
right. Against a real message, only the library's mapping yields self-consistent
OHLC; the documented one gives an open of 779 on a $421 stock and a high below
the low.

### Breaking changes

- Option quotes are relabeled with `STRIKE_PRICE` where they previously used
  `STRIKE_TYPE`. The enum member `STRIKE_TYPE` still resolves, so only code
  reading the key out of a relabeled message is affected.

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
