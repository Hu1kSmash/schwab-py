# Changelog

This is a maintained fork of [`alexgolec/schwab-py`](https://github.com/alexgolec/schwab-py).
Versions below 1.6.0 are upstream releases; see the upstream repository for their notes.

Through 2.1.0, changes here were offered upstream as pull requests first, so that anything
upstream merged would shrink the divergence this fork carries. Upstream merged none of them, and
its maintainer confirmed in September 2026 that he does not intend to update the project. As of
2.2.0 this fork no longer tracks upstream and no longer maintains compatibility with it; see
`MAINTAINING.md` for what that changed and what it did not.

Entries below 2.2.0 were written under the old arrangement, and some of them discuss which changes
had or had not been sent upstream. They are left as written rather than rewritten to match the
current model.

---

## Unreleased

### Documentation

**The `ACCT_ACTIVITY` `MESSAGE_TYPE` tokens were documented in the wrong case,
and one of them in the wrong spelling.** Measured on 2026-09-05 by driving the
states deliberately against a live account: the tokens are CamelCase on the
wire — `OrderCreated`, `OrderAccepted`, `CancelAccepted`, `ExecutionCreated`,
`OrderUROutCompleted` — with `SUBSCRIBED` a genuine exception.

A consumer comparing against `'ORDERCREATED'` matched nothing. Worse,
`ORDERUROUT` is not a case variant of `OrderUROutCompleted`, so upper-casing
does not rescue it — and at least one consumer had copied that token from this
list, where it would have alerted on an ordinary cancel.

The two sequences a caller most needs to tell apart are now written down: a
cancel you issue yourself, and a buy rejected for buying power. They differ only
by `ExecutionCreated`, and the rejection returns **HTTP 201 with a real order
id** and only becomes `REJECTED` about a second later — so a caller checking
only the HTTP status believes it worked.

**Five more `ACCT_ACTIVITY` `MESSAGE_TYPE` tokens.** `ORDERMONITORCREATED`,
`ORDERMONITORCOMPLETED`, `CHANGECREATED`, `CHANGEACCEPTED` and
`EXECUTIONCREATED` — the lifecycle of a resting limit or stop order, observed on
a live feed on 2026-07-27. A program placing only market orders never sees them
and will meet them the first time a human places an order by hand in the same
account, which is a plain way to get an unknown-shape alert from an allow-list.
The note also flags that `CHANGECREATED`/`CHANGEACCEPTED`/`ORDERREPLACED` mean a
*working order was amended* — a safety event for an order you placed yourself.

### Fixed

**CI was red on macOS on every tag since 2.0.0, and the README badge said
otherwise.** Seven `ClientFromLoginFlowTest` cases really start the callback
server in a child process and talk to it over loopback; on the macOS runners
the child starts and never answers on its port, so each fails after the full
30-second wait, on every Python version. Windows passes, and Windows also spawns
rather than forks, so this is not a start-method problem.

They are skipped on macOS CI runners only — not on a developer's Mac — with a
comment saying what would settle whether this is a runner restriction or a real
macOS defect. The other 923 tests pass on macOS and that coverage is kept.

## 2.4.0

### Added

**`add_error_handler` now reports a fourth kind of absorbed failure: a message
this client cannot use at all.** A frame which is not an object, an element of
`data` or `notify` which is not an object, a `service` which is not a name.
These arrive as the new `UnusableMessage`, whose `message` is the offending
value as it arrived, with `cause` (the exception that made it unusable, where
there was one) and `count`/`total` as integers — reports are suppressed after
the first few, so the counts are the only way to see the true scale, and a
consumer alerting on drop volume should not have to parse them out of prose.

That callback exists so an absorbed failure is not visible only in a log, and
these are absorbed failures. A consumer who registered a handler to stop
scraping logs would otherwise watch a subscription go silent after a framing
change with no programmatic signal at all — the state 2.2.0 added the callback
to eliminate.

`UnusableMessage` rather than the existing `UnparsableMessage`, which means the
JSON did not decode and carries the parse exception. Here the JSON is fine and
the structure is not; one type meaning two shapes is a trap this library has
been bitten by before.

### Changed

**A systematically malformed channel no longer logs one line per element.** The
first three on a connection are logged, then powers of ten, with the running
count. A framing change on a `LEVELONE_EQUITIES` subscription across a few
hundred symbols would otherwise produce a warning per element per tick
indefinitely — a log-volume incident on top of the data outage.

Reports are coalesced onto the same schedule for a second reason: they share a
bounded queue with the late rejections, so reporting every occurrence would let
a flood of unusable elements evict a rejection of an abandoned request, which is
the one thing nothing else will ever report.

### Fixed

**A malformed message ended the caller's receive loop.** Four related cases,
all of which raised out of `handle_message` where the caller could only read
them as the stream having failed:

* an element of `data` or `notify` which is not an object — `d.get('service')`
  is evaluated at the dispatch call site, outside the `try` that protects
  handlers;
* a `service` which is not a name, since the handler lookup is evaluated in the
  same place;
* a frame which is not an object at all — a top-level JSON array or string;
* a top-level JSON `null`, which was indistinguishable from the internal
  sentinel meaning "this response was routed to its waiter", so it was dropped
  without even a log line.

Each is now logged and skipped, and well-formed elements beside a bad one are
still dispatched.

**A failure to relabel a message was reported as a handler failure.** Relabeling
is this library's work, not the caller's, but it happens inside the per-handler
`try` — so a `content` the field tables could not read was reported as "your
handler raised", once per registered handler, uncounted and uncoalesced. It is
absorbed once per message now, and it carries the `service` it belongs to and
the exception that caused it: `_BookHandler` indexes four levels deep, so the
`KeyError` is the only thing that says which field moved.

**A response frame with an unreadable request id was logged and nothing else.**
It was the one unusable-message path that bypassed the counting and the
callback — so it repeated per re-read inside a single subscribe, and a venue
emitting a non-numeric `requestid` gave a consumer no programmatic signal at
all.

**An `UnusableMessage` could not be told from a failure to close after logout.**
Both arrived as `service=None, message=None`, which the documentation designates
as the close-failure signature. The report now carries the containing frame as
`message`, which is non-`None` for every case but a top-level JSON `null`, and
the documentation says to test `isinstance(exception, UnusableMessage)` rather
than branching on both being unset.

**A custom JSON decoder returning anything but `dict` and `list` broke the
stream.** `set_json_decoder` is a public hook which promises only "the decoded
JSON", but the type checks above were written against the concrete types, so a
decoder returning a `Mapping` which is not a `dict` — or tuples for arrays — had
every frame dropped, presenting as a permanently dead feed with no exception.
The checks are against the operations used, not against `collections.abc` — an
ABC matches only real subclasses and registered types, which would have narrowed
what a decoder may return rather than tolerating it. A JSON array must be
**indexable**, which tuples are: routing reads `frame['response'][0]`,
validation reads it again, and handlers get the frame afterwards, so a
single-pass iterable cannot serve however tolerant the iteration is. One is now
refused and reported rather than accepted and found empty by whichever function
read it second.

Separately, and cosmetically: the debug log formatted frames with `json.dumps`,
which refuses such an object. Logging swallows a formatting failure, so the
stream survived either way, but the content of every debug line was replaced by
a traceback — for exactly the people who customised the decoder and are most
likely to be reading it.

**A mismatched request id was reported as a malformed frame.** All five fields
were read before any was compared, so a frame carrying an id this client never
issued *and* missing another field said `malformed response frame: KeyError:
'service'`. The id mismatch is the more diagnostic fact — it means the server
and this client disagree about what was asked — and it was hidden behind
whichever field happened to be absent. The id is compared before the rest is
read.

**`set_json_decoder` looked its base class up through `schwab.contrib.util`,**
which raises `AttributeError` unless the caller happened to have imported that
module. Someone subclassing `StreamJsonDecoder` where it is actually defined,
in `schwab.streaming`, has no reason to have done so. It is the same class
either way; the local name is used now.

**A malformed answer took down the receive loop as well as its own request.**
`_validate_response` read four fields straight after the request id, unguarded.
A `KeyError` there reached `_fail_pending_request`, which sets the exception on
the waiting future *and* re-raises — so one unreadable field failed the request
with a bare `KeyError` and ended the caller's `handle_message` loop with it. A
frame too malformed to check is now returned as an `UnexpectedResponse` saying
so, which fails that request and leaves the stream usable.

Found by sweeping for the shape of the 2.3.0 fix rather than waiting for a
report: 2.3.0 guarded the request-id read, and this sat four lines below it.

A rejection carrying a code but no `msg` is also no longer treated as an
unreadable frame. The code is the part a caller can act on, and losing it to a
missing message field was the worse outcome.

### Documentation

**`pip freeze` drops the extra from a pinned line, and says nothing.** A
requirements file carrying `schwab-py[login] @ git+...@v2.3.0` installs
correctly, but freezing that environment writes `schwab-py @ git+...@<sha>`
back out, and installing from *that* silently omits `flask`, `multiprocess` and
`psutil`. The failure surfaces later, when something first calls the login flow.
Documented in `docs/getting-started.rst`. This is a `pip` limitation with direct
URL requirements, not something this package can fix.

## 2.3.0

### Changed

**The login flow and the code generator are now optional extras.** A plain
install requires three packages -- `authlib`, `httpx2`, `websockets` -- and
nothing else. `flask`, `multiprocess` and `psutil` move to `schwab-py[login]`;
`autopep8` moves to `schwab-py[codegen]`.

**This is breaking if you use `client_from_login_flow` or `easy_client`.** Add
`[login]` to your install. Calling either without it raises an `ImportError`
that names the extra and gives the command, rather than a bare "No module named
'flask'".

Note the second one carefully: **`easy_client` needs `[login]` even when you
already have a token file.** Its `max_token_age` defaults to 6.5 days, and a
token older than that is discarded and replaced through the login flow. So a
plain install works for 6.5 days and then fails on a routine re-authentication,
which on an unattended machine is the worst shape this break can take. Pass
`max_token_age=0` to disable the proactive refresh if you really want to run
`easy_client` without the extra — but Schwab's refresh token expires seven days
from authorization regardless, so anything long-running needs a way to log in
again either way.

In a Jupyter or Colab notebook `easy_client` routes to `client_from_manual_flow`
instead, which starts no callback server, so notebook users need no extra.

Not affected: `client_from_token_file`, `client_from_access_functions`,
`client_from_received_url`, `client_from_manual_flow`, and the streaming client.
None of them touch the callback server.

Measured on a clean 3.14 install: 27 packages before, 15 after. The twelve that
go are `flask` and its tree (`blinker`, `click`, `itsdangerous`, `jinja2`,
`markupsafe`, `werkzeug`), `multiprocess` and `dill`, `psutil`, and `autopep8`
with `pycodestyle`.

None of them were ever used outside the interactive login flow and the code
generator, and two -- `multiprocess` and `psutil` -- were imported at module
scope, so every `import schwab.auth` paid for them. A process that loads a token
from a file and streams quotes has no use for a web framework, and on a machine
that places trades each package is something to patch, audit and break on
upgrade.

### Fixed

**A malformed response element ended the caller's receive loop.** A `"content"`
present but JSON `null` made `content.get('code')` raise `AttributeError` out of
`handle_message`. Both framings of the same event now share one parser, so a bad
element is logged and skipped and the good elements beside it still report —
they had diverged, with one framing hardened and the other not, which is exactly
what the framing-independence contract above says cannot happen.

**`login()` did not close the connection it replaced.** Calling it on a healthy
client — a re-authentication, a preferences refresh — dropped a live websocket
and its reader with nothing closing it. After a `ConnectionClosed` the old
socket is already gone and this is a no-op, which is why it went unnoticed. A
failure to close is logged rather than raised, since the login is the operation
the caller asked for.

**A rejection riding along in a matched response frame was reported by
nothing.** `_validate_response` reads `response[0]`, which is the answer to the
outstanding request; a frame carrying a second response handed it to the waiter
unexamined. If that one was a rejection, nothing mentioned it -- the same gap
the late-rejection reporting closed in 2.2.0, one element along. Additional
responses are now checked. A rejection logs a warning and is reported to
`add_error_handler`; a success alongside the answer logs at INFO and is not
reported, exactly as on the orphan path.

The rule is that every response no waiter claimed is checked, which is usually
everything past element 0. In the window where a waiter has already timed out
but the pending slot is not yet cleared, nobody claims element 0 either, and it
is checked too.

Reporting it matters more than it might look. `_request_lock` keeps one request
outstanding, so a second response in a frame cannot answer anything the client
is waiting on — it is a late answer to an abandoned request, the same class the
orphan path has reported since 2.2.0. Whether Schwab sends it in its own frame
or batches it behind the answer to a live request is the server's choice. Had
only the orphan framing reported, a consumer who replaced log-scraping with
`add_error_handler` would see a rejection one day and silently miss the
identical one the next, for a reason invisible to them.

**But not from where it is found.** That code runs holding the read lock, on the
request path the request lock too, and inside the response deadline — a user
handler called there let a slow one turn a subscription that *succeeded* into a
`ResponseTimeoutError`, and one that re-subscribed blocked on a lock its own
caller held. Both were real, and both have tests. The report is queued instead,
and delivered by whichever coroutine read the frame once it has released its
locks: before `handle_message` returns, or before the request that read it
returns. Draining only in `handle_message` was not enough — when a subscribe
wins the read lock, `handle_message` can be parked in `recv()` with its own
drain already behind it, and the report would then wait for the next inbound
message, which on a quiet stream is unbounded.

The consequence to know: **your error handler can be called from inside a
subscribe.** A slow one delays that call returning; it cannot make it fail. A
request delivers what it read even when it fails, since the exception the caller
gets describes only the response that answered their own request — though a
handler's `BaseException` is logged rather than allowed to replace it, and a
*cancelled* request skips the report so a shutdown never waits on user code. The queue is
bounded, and is cleared by `close()` and by a fresh `login()`, so a torn-down
session's rejection is never reported against a new one whichever way the caller
reconnects. Frames read but not yet handled are cleared with it — that deque
predates this change and had the same leak, which would have left the standalone
framing crossing sessions while the batched one did not, and could hand a
handler a quote from a dead connection. The log line written when each
rejection is found is the complete record; the callback is the convenience. All
of this is stated in `add_error_handler`'s docstring and in `docs/streaming.rst`.

## 2.2.0

### Added

**`StreamClient.add_error_handler`.** A stream handler which raises is logged
and skipped, and a connection which fails to close after logout is logged. Both
are the right behaviour, and both leave the caller with a log record rather than
something to react to. The only way to react was to attach a `logging.Handler`
and match on message text, which every consumer who cared had to write and which
coupled them to strings this library is free to reword.

```python
def on_stream_error(service, exception, message):
    alert('schwab stream: %s raised %r' % (service, exception))

stream_client.add_error_handler(on_stream_error)
```

Registering none keeps the existing behaviour exactly, and the log line is
written either way.

It reports three kinds of failure: a stream handler which raised, a late
rejection of a request nobody was waiting on, and a connection which failed to
close after logout. The middle one is the least obvious and the most
actionable -- the request was abandoned, so nothing else will ever say Schwab
refused it.

Handler failures are wired at two places in the code, not one. A synchronous
handler's exception passes through an `except` block; an asynchronous handler's
does not -- it surfaces in the task's done callback, at a different logging
level, in a different function, with no `except` around it. Wiring only the
`except` clauses would look complete and cover synchronous handlers only, which
for this purpose is worse than none: it turns "no signal" into "a signal, and it
is quiet". There is a test that fails if the async site is left unwired and
passes if only the synchronous one is checked, and the async case asserts on the
service name as well as the exception -- reporting it as `None` would satisfy a
weaker assertion while making "mark this subscription unhealthy" impossible.

The handler may be a coroutine function, like every other handler on this class,
and it is **awaited** rather than scheduled — the report finishes before the call
that found the failure returns. That keeps the report reliable with no machinery
to keep it alive: nothing to drain at shutdown, so nothing that can deadlock,
time out or be cancelled half-delivered while draining. The cost is that the
handler runs on the path that found the failure, so a slow one holds up
`handle_message`, exactly as a slow synchronous handler always has. Hand off to
your own task if you need to do something slow.

A handler of the wrong shape is refused at registration rather than discovered
at report time. Every other `add_*_handler` here takes a one-argument callback,
so `add_error_handler(lambda exc: ...)` is the natural mistake -- and it would
raise `TypeError` on every report, inside the `except` clause that exists to
stop an error handler failing the stream, so it would never run and never say
so.

### Documented

**Relabeling is not applied uniformly, and the docs said nothing about it.**
Content on the `data` channel is relabeled from numeric field ids to names.
Content on the `notify` channel is forwarded unchanged, ids intact. Both reach
the same handlers, so a handler assuming relabeling mis-parses a notify frame --
by finding nothing rather than by raising, since the keys it looks for are
simply absent. The Data Field Relabeling section explained the mechanism and
never mentioned the exception.

**What `ACCT_ACTIVITY` payloads actually look like.** Schwab documents the
three top-level fields and nothing inside `MESSAGE_DATA`, so every consumer
reverse-engineers it privately. The order identifier appears under seven
spellings, the symbol under four, and both `CANCELED` and `CANCELLED` occur in
Schwab's own status tokens. That is now written down, collected by watching a
live feed over roughly a year, and labelled as an observation log rather than a
contract -- nothing in it is validated by this library, and a shape that has not
been seen is not thereby impossible.

### Changed

**This fork no longer tracks upstream.** Through 2.1.0 every change was branched from a mirror of
`alexgolec/schwab-py` and offered as a pull request before being merged here, on the reasoning that
anything upstream took would shrink the divergence. Upstream merged none of them, and its
maintainer confirmed in September 2026 that he does not intend to update the project.

So the arrangement had become a ritual with a real cost: the last several changes were cut from
`main` because they could not sensibly be cut from anywhere else, and each needed a paragraph
explaining why it had not been sent. Topic branches now come from `main`, there is no PR queue, and
changes are made because they are right for this library rather than because upstream might take
them. `MAINTAINING.md` records what this changed and what it did not.

Nothing about the code's authorship changes. This is still overwhelmingly Alex Golec's work, the
licence and attribution are untouched, and if upstream ever resumes, `upstream-main` is still
mirrored here and reconciling with it beats defending the fork.

## 2.1.0

> **This is a breaking release despite the minor version.** It removes three
> deprecated APIs and changes how `decimal.Decimal` prices are rendered. The
> number is minor because this fork is installed from pinned tags rather than
> version ranges -- nothing upgrades into it by accident -- but if you are
> moving from 2.0.x by hand, read this section rather than skimming it.

### Removed

Three APIs which had been deprecated with warnings. All three are breaking for
code still using them, and all three fail loudly at the point of use rather
than changing what an order or a subscription means.

**Prices must be strings.** `set_price` and `set_stop_price` used to accept
any number and truncate it -- two decimal places, or four below one. Passing a
number now raises `ValueError` naming the fix.

Note this includes **integers**: `set_price(1250)` raises, not just
`set_price(1250.0)`. Integer prices were the form this project's own
documentation used, so auditing your call sites for float literals alone will
miss some. The removed helper was named `truncate_float`, which is worth
searching for too -- it was a public module-level name, and anything importing
it now gets an `ImportError`.

The conversion was removed rather than kept because the library was choosing a
rounding, for a value denominated in money, on behalf of a caller who knows
what the order is for. Whether a limit should round up, down or to the nearest
tick is a trading decision.

**`'{:.2f}'.format(value)` is not an equivalent.** It rounds; the old code
truncated toward zero, and used four decimal places below one. `19.9999999`
became `19.99` rather than `20.00`, and `0.186992` became `0.1869` rather than
`0.19`. On a buy limit that difference is a price one tick higher than the one
asked for. The docs carry the exact `decimal.ROUND_DOWN` equivalent for anyone
who wants to migrate without moving any prices.

**`decimal.Decimal` now passes through exactly, where it used to be truncated.
This one is a silent change and the only one in this release.** A `Decimal` was
not a `str`, so it fell through to the same conversion floats did:
`set_price(Decimal('12.129'))` sent `'12.12'` up to 2.0.1, and sends `'12.129'`
now. If you compute prices as `Decimal` and relied on the library to round
them, it no longer will, and a sub-penny equity limit is rejected by Schwab
rather than caught here.

That is the intended behaviour rather than an oversight -- a `Decimal` carries
the precision its author chose, and silently discarding it was the bug -- but
it is a change to what a previously correct call puts on the wire, so check
your `Decimal` call sites. It is rendered with `format(d, 'f')` rather than
`str(d)`, because `str(Decimal('1E+2'))` is `'1E+2'`, which is not a price.

**Build a `Decimal` from a string, not a float.** `Decimal(0.1)` is that
float's binary expansion to 55 decimal places, and rendering it exactly -- the
point of accepting `Decimal` at all -- puts all 57 characters on the wire. Up
to 2.0.1 the truncation hid this.

It is not refused. A guard on decimal places was written for this release and
then removed, because measuring it showed the guard could not do what it
claimed: over realistic inputs, float-derived values span 0 to 53 decimal
places while string arithmetic spans 1 to 9, so no threshold separates
contamination from an honest computed limit. What a threshold does reliably is
refuse a valid price at order-placement time. And the payload it prevents is
merely long, not wrong -- Schwab types both `price` and `stopPrice` as
`number($double)`, so a 57-character spelling parses to the same double a short
one does.

So `Decimal(str(value))` is a habit this library recommends and does not
enforce, and rounding a computed price stays your decision:
`value.quantize(Decimal('0.01'))`.

`copy_price` and `copy_stop_price` still skip the type check, which is what
`contrib.orders` uses to reconstruct a historical order. They do refuse a
non-finite `Decimal`, since rendering one produces the transmittable string
`"NaN"`; `float('nan')` is still accepted there because it does not survive
serialization -- `httpx2` builds request bodies with `allow_nan=False`, so the
request raises before it is sent. Note that a bare `json.dumps` of the built
order does *not* raise: it emits the invalid-JSON token `NaN`. If you serialize
a spec yourself for logging or a diff, that is what you will see.

**`websocket_connect_args['extra_headers']` is no longer translated.**
websockets 14.0 renamed it to `additional_headers`; this library had been
rewriting it silently and warning. Passing it now raises `ValueError` naming
the replacement, as `create_protocol` and `read_limit` already did.

The argument is documented as a passthrough to `websockets.connect()`. Quietly
substituting one name for another on the way through is not a passthrough, and
it meant the name a caller wrote was not the name the library called.

**`LevelOneOptionFields.STRIKE_TYPE` is gone.** It was an alias of
`STRIKE_PRICE`, kept when field 20 was renamed to what Schwab actually
documents it as. Code naming it now raises `AttributeError` instead of reading
a field whose messages are labelled something else.

### Fixed

**`Decimal` is for the price fields only, and is refused elsewhere at the
setter.** `quantity`, `activationPrice`, `stopPriceOffset` and `priceOffset`
are `number($double)` in Schwab's schema, so passing a `Decimal` to one raises
where the field is still known.

This is narrower than it may read: a plain `str` in those fields is still
accepted and still produces a string where Schwab's schema says number.
`Decimal` is refused because this library would be the one rendering it, which
is a choice it should not make silently; a string is what the caller wrote.
Whether to refuse that too is a separate question, not settled here.

**`copy_price` and `copy_stop_price` could not take a `Decimal`.** They skip
validation by design, so a `Decimal` reached the object builder raw -- and
having no `__dict__`, it fell to the reflection path and raised `vars()
argument must have __dict__ attribute` from `build()`, far from the call that
caused it and naming neither the field nor the type.

**A non-finite `Decimal` now raises a clear error from every numeric setter.**
`_assert_finite` reads `float(Decimal('sNaN'))` raising `ValueError` as "not a
number at all" and returned, so a signalling NaN reached the `<= 0` comparisons
in the setters and raised a bare `decimal.InvalidOperation` whose message is a
repr of its own class -- the exact failure that check runs first to prevent.
2.0.x refused these too, just unreadably; this is a diagnosis fix, not a safety
one. (`Decimal('sNaN')` never reached an order in a released version. It could
briefly during this release's development, which is why the test exists.)

**`OptionSymbol` accepted a non-finite strike.** `float('nan')` parses and
`nan <= 0` is `False`, so `'nan'` and `'inf'` passed the constructor's
positivity check and failed later inside `build()` as `cannot convert NaN to
integer`, naming neither the strike nor the symbol. They are refused at
construction now, next to the positivity check.

**`OptionSymbol` accepted strikes it could not encode.** (The checks that
enforce this are exact regardless of the process-wide `decimal` context. They
read the parsed strike's own digits rather than scaling it first, because
multiplying consults the context and no fixed precision covers every input.) The symbol's strike
field is eight digits of thousandths, so it cannot carry more than three
decimal places and stops just below `$100,000`. Neither limit was checked: a
strike of `2.0019` was truncated to `00002001`, naming a `$2.001` contract, and
`0.0005` became a strike of zero, while `700000` widened the field and produced
a 22-character symbol. Both are refused at construction now, where the strike
is still in hand, rather than producing a symbol for a different contract or
none.

**Option symbols encoded some strike prices a tenth of a cent low.**
`OptionSymbol.build()` scaled the strike by 1000 as a binary float and
truncated with `int()`, which truncates the representation error along with the
value: `2.01 * 1000` is `2009.9999999999998`, so the symbol came out
`...C00002009` rather than `...C00002010` -- a different contract, or one that
does not exist. 590 of the 100,000 cent-granular strikes between `$0.01` and
`$1000.00` were affected, on the order-placement path.

This is the same defect that made limit prices a cent low, in a different
function, and it survived the fix to that one. It now scales in `decimal`,
which is exact: the strike is already validated as a string on the way in.

### Note

The three removals convert a silent accommodation into an error, so code which
already passed strings, used `additional_headers` and named `STRIKE_PRICE` is
unaffected by them.

The `Decimal` change above is the exception, and the only thing here that
alters a working call without raising. If you pass `Decimal` prices, read that
paragraph.

## 2.0.1

### Documented

**2.0.0 moved where TLS trust comes from, and did not say so.** `httpx` depended on
`certifi` and built its default SSL context from the CA bundle shipped inside that
wheel. `httpx2` does not depend on `certifi` at all -- it uses `truststore`, which
reads the **operating system** trust store:

```
httpx/_config.py    create_ssl_context -> import certifi
                    ssl.create_default_context(cafile=certifi.where())

httpx2/_config.py   create_ssl_context -> import truststore
                    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
```

Two things follow, neither of which is a defect, but both of which are worth
knowing before you move this onto a new host:

- **TLS now depends on the host having a populated CA store.** A slim or distroless
  container without `ca-certificates` worked on 1.11.4, because the bundle travelled
  inside the `certifi` wheel. On 2.0.0 and later, certificate verification fails and
  surfaces as `httpx2.ConnectError`. It will not hide: nothing in this library
  catches that outside the login flow's readiness probe, so it reaches your caller
  on every request rather than being absorbed and retried. A sudden run of connect
  errors immediately after a host or image change is this, not the network.
- **The trust set is whatever the OS trusts.** An interception or corporate root
  installed in the host store is now trusted for Schwab traffic, where previously
  only certifi's bundle was. That is a real change in posture for a process holding
  tokens with full account access.

`SSL_CERT_FILE` and `SSL_CERT_DIR` still override, if you would rather pin the trust
set explicitly than inherit the host's.

### Removed

**Four dependency declarations that nothing imports.** `certifi` was there to keep a
current CA bundle in the `httpx -> httpcore -> certifi` chain, which 2.0.0 removed;
leaving it declared implies a bundle that is no longer in the path. `urllib3`,
`python-dateutil` and `nose` are referenced nowhere in the library, the tests or the
tooling.

**A warning suppression which could never fire.** The login flow's readiness probe
wrapped its `verify=False` request in a filter for
`urllib3.exceptions.InsecureRequestWarning`. `urllib3` is not in `httpx2`'s stack and
was not in `httpx`'s either; measured against a self-signed local server, `httpx2`
emits no warning at all on `verify=False`. The filter, the `urllib3` import and two
`-W ignore::urllib3.exceptions.*` entries in `tox.ini` are all gone.

### Fixed

**`make release` uploaded to PyPI with the tests switched off.** It ran
`twine upload dist/*` against `schwab-py`, which on PyPI is the *upstream* project --
so it would have replaced someone else's package with this library under their name.
The test step had been commented out with a `# TODO: Reinstate tests before
releasing` left in place. Inherited from upstream, where publishing to PyPI is
correct. There is now no release target: it prints why and exits non-zero, and
points at `MAINTAINING.md`. `make coverage` ran `nose`, which does not work on any
Python this project supports, and `make dist` used the deprecated
`setup.py sdist bdist_wheel`.

**`requests` was used by the test suite and declared nowhere.** It arrived only
because `twine` pulls in `requests-toolbelt`. It is now a dev dependency in its own
right.

## 2.0.0

### Changed

**This library now uses `httpx2` rather than `httpx`, and requires Authlib
1.8 or later.** Both are breaking changes for anything that catches an
exception from a client call or type-checks a response.

Authlib 1.8 stopped importing `httpx` directly. Its `httpx_client` integration
imports `httpx2` when that package is installed and falls back to `httpx` when
it is not, emitting a deprecation warning it forces past the default filters.
The fallback is documented as temporary. Since `OAuth2Client` inherits from
whichever module Authlib resolved, the client's response and exception types
were being decided by whatever else happened to be installed.

`httpx` and `httpx2` share no hierarchy: `httpx2.Response` is not
`httpx.Response`, and `httpx2.HTTPStatusError` is not a subclass of
`httpx.HTTPStatusError`. Disagreeing with Authlib therefore fails silently
rather than loudly -- an `isinstance` check stops matching, an `except` clause
stops catching, and only in production, where the response comes from Authlib's
session rather than from a test which constructed its own.

**If you catch `httpx` exceptions around calls into this library, or check
responses against `httpx` types, those now need to name `httpx2`.** Catching a
tuple of both is a way to cross the change without a flag day.

Declaring `httpx2` alone would not have been enough. The previous floor of
`authlib>=1.6.0` left Authlib 1.7.2 with `httpx2` installed a legal
resolution -- Authlib on `httpx`, this library's guards on `httpx2`, every
guard silently dead. The floor moved to `authlib>=1.8` for that reason.

### Added

**A test that a half-finished version of this change cannot pass.**
`tests/http_module_test.py` compares the module Authlib built `OAuth2Client`
on against the module each guarding file imported, and fails when they differ.

It was needed because nothing else could see the problem. Every other test in
the suite constructs the type it then asserts on, so the whole of it passed
against Authlib 1.8 with `httpx2` installed while the library still guarded on
`httpx` -- 824 of 824 green, on 3.12 and 3.14, in exactly the configuration
where `add_child_order_strategy` no longer recognises a response and the login
flow's readiness wait no longer absorbs a refused connection.

## 1.11.4

### Fixed

**A test added in 1.11.3 raced a server it never started.** The new coverage
for the connect-timeout case mocked the readiness check to report success, then
let the flow open a browser whose stub makes a real request to the callback
port -- where nothing was listening, because the readiness check was a mock.
Local timing hid it; one CI runner did not:

```
ConnectionRefusedError: [Errno 111] Connection refused
FAILED test (ubuntu-latest, 3.12, py312)
```

No library change. The test now delivers no callback and asserts on the timeout
plus the attempt count, which is what it was actually for.

## 1.11.3

Cross-platform. This fork's CI runs Linux on every push and all three platforms
on tags, and the tag builds had been red on macOS and Windows for as long as
that matrix has existed -- while the badge, which tracks the default branch,
stayed green on Linux. Nobody looked.

### Fixed

**A connect timeout ended the login flow instead of being waited through.**
`client_from_login_flow` starts a local server and polls it until it answers,
catching `httpx.ConnectError` for "not listening yet". Whether an unbound port
refuses a connection or silently drops it is a property of the host: a firewall
drops, and so do the macOS runners. A dropped attempt raises
`httpx.ConnectTimeout`, which is a *sibling* of `ConnectError` rather than a
subclass --

    ConnectError    -> NetworkError     -> TransportError
    ConnectTimeout  -> TimeoutException -> TransportError

-- so it escaped and took the login flow down while the server was still
starting. Every login-flow test fails on macOS for this reason. It is not a
test-only problem: on a machine that drops rather than refuses, the login flow
could not complete at all. Offered upstream as #264.

### Documentation

**The token file is not protected on Windows, and the docs said it was.**
Windows has no POSIX file mode -- `os.chmod` toggles a read-only bit and
ignores the rest -- so the token is left readable by any account on the
machine. The docs stated flatly that it is written mode `0600`. For a file that
grants full access to a funded account, claiming a protection that does not
exist is worse than claiming nothing. Now a warning saying what a Windows user
should do instead, and noting that the atomic-write and durability properties
*do* hold there; only the permission narrowing does not.

The test asserting mode `0600` is now skipped off POSIX rather than relaxed to
something both platforms satisfy, which would have stopped it meaning anything
where it matters.

### Notes

Every "tests passing" figure reported during the 1.9.0-1.11.2 work was Linux
only, and said so nowhere. The macOS and Windows columns existed the whole
time.

## 1.11.2

A second review, over the whole divergence from 1.5.0 rather than the last
release. One serious defect and four small ones.

### Fixed

**A late stream response wedged every request that followed it.**
`_read_and_route` checked each response frame against whichever request was
pending and, on a mismatch, failed that request with it. So the late answer to
an abandoned request killed an unrelated one -- and was consumed doing it,
leaving the next stale answer for the next request:

```
request 1: ResponseTimeoutError (timed out)
request 2: UnexpectedResponse: unexpected requestid: 0
request 3: UnexpectedResponse: unexpected requestid: 1
request 4: UnexpectedResponse: unexpected requestid: 2
```

One client-side timeout and the stream never completed another request. 1.9.0
taught `handle_message` to tolerate an orphaned response; this is the same
tolerance one level down, where the routing happens. Since this fork added
`DEFAULT_RESPONSE_TIMEOUT`, it supplied the trigger as well as the fault.

The rule is bounded on both sides: an id issued *earlier* is lateness and the
frame is handed back as an orphan, while an id never issued is genuine
protocol confusion and still fails, as it always has.

**The library warned about a datetime it invented itself.**
`get_price_history_every_day('AAPL')`, with no dates at all, warned about
`start_datetime` and blamed the caller's line -- the loudest possible false
alarm from 1.9.0's warning, on the most common way these endpoints are called.
The substituted default was naive, so the check could not tell it from
something a caller wrote. It also made the `startDate` for an unparameterized
call depend on the host's offset. Now explicitly UTC, and the suite passes
identically under four timezones, which it did not before.

**`priceOffset` was dropped when repeating an order.** `contrib.orders` knew
`priceLinkBasis` and `priceLinkType` but not the offset those apply to, so
`construct_repeat_order` returned a price-linked order with no offset -- a
different order at a different price, silently. `set_price_offset` is this
fork's own addition, which is why the table never grew an entry for it.

**A mangled link.** The fork's URL rewrite broke a string concatenation in
`add_child_order_strategy`, leaving `.../docs/index.rstorder-templates.html`,
a 404.

**A docstring promised a guard one configuration does not have.** Passing a
collection of order statuses raises `ValueError` with the enum check on, and
does not with `enforce_enums=False` -- which `client_from_login_flow` defaults
to. Now qualified.

### Notes

The `priceOffset` gap survived the audit's own round-trip probe, which
reported 48 of 48 templates identical. None of those templates uses a
price-linked order, so the number said nothing about the field. A probe that
passes because it never exercised the case is the same failure as a test that
passes either way.

1.11.1 shipped a comment claiming the path separator in the frame walk could
not be tested without a real sibling package on disk, and concluded it was
untestable. The first half was right; the conclusion was not. Building that
layout on disk is about ten lines, and there is now a test which fails when
the separator is removed.

## 1.11.1

A final audit of the audit. Everything here is a defect in something 1.9.0
through 1.11.0 introduced -- three of them in guards which did not guard as
much as they claimed.

### Fixed

**The finite-number check covered only prices.** It missed the other numbers
in an order, and it missed the worse case: the existing positivity guards do
not catch NaN, because NaN compares False against everything. `quantity <= 0`
and `activation_price <= 0.0` are both False for it.

```python
OrderBuilder().set_activation_price(nan).set_stop_price_offset(nan)
              .set_quantity(nan).build()
# {'quantity': nan, 'stopPriceOffset': nan, 'activationPrice': nan}
# json.dumps → {"quantity": NaN, ...}   which is not valid JSON
```

Those are the fields a trailing stop and a conditional order use.
`set_quantity`, the order legs, `set_activation_price`, `set_stop_price_offset`
and `set_price_offset` now check before the positivity comparison. Offered
upstream as #262.

**A locally-unusable token was reported as retryable.** `MissingTokenError`
and `InvalidTokenError` are `OAuthError` subclasses which authlib raises
*before any HTTP call*, when the stored token has no refresh token or cannot
be used. They arrived with `refresh_token_invalid=False` and a message saying
the failure "may be transient", so an application following the documented
pattern retried forever on a permanent, purely local condition -- the exact
failure the attribute exists to prevent, reached through the attribute.
Offered upstream as #266.

**The naive-datetime warning blamed the library, not the caller.** A fixed
`stacklevel` cannot be right when the endpoints sit at different depths --
`get_price_history_every_day` wraps `get_price_history`, and
`get_orders_for_account` goes through `_make_order_query`. Two of the four
entry points pointed at `base.py`, which tells a caller nothing they can act
on. The frames are now counted. Offered upstream as #259.

**The bug-report log guard missed a broken pipe.** It caught `ValueError` but
not `BrokenPipeError`, which is an `OSError`, so `python bot.py 2>&1 | head`
still produced the "Exception ignored in atexit callback" traceback the guard
was added to remove. Offered upstream as #257.

**A rejected subscription became invisible.** 1.9.0 stopped an orphaned stream
response from ending the receive loop, which was right, but logged every one
at INFO -- including failures. The request was abandoned, so nothing else ever
reports that Schwab refused it. Non-zero codes now log at WARNING. Offered
upstream as #261.

### Changed

**The token temp-file sweep waits five minutes rather than one.** The
threshold is not a tidiness knob, it is the entire mechanism keeping the sweep
from deleting a file a *different* process is still writing -- which was
demonstrated, and costs that process its token update. Widened, with the
reasoning moved into the constant, and the assumption that mtime and the local
clock agree written down for anyone on a network mount.

### Notes

Two of these were found because a test passed when it should not have. The
warning-attribution fix shipped with an off-by-one that a filename-only
assertion could not see, and the sweep's concurrency test used a file created
that instant, which survives any threshold. Both tests now fail against the
code they are meant to catch.

One thing is deliberately untested and says so in the source: the path
separator in the frame walk's prefix comparison. Reaching it needs a real
sibling package on disk, and every test written for it passed with the
separator removed.

## 1.11.0

### Added

**`TokenRefreshError.refresh_token_invalid`, saying whether a retry can work
at all.** 1.10.0 reported the token's age and left the caller to infer the
rest. This makes the inference directly.

A refresh token Schwab has rejected as invalid cannot be retried back to life:
a new one comes only from the authorization_code flow, which needs a human at
a browser. An unattended application which treats that like a dropped
connection keeps asking, and the endpoint it hammers is the one its own
recovery depends on.

```python
try:
    r = c.get_quote('AAPL')
except TokenRefreshError as e:
    if e.refresh_token_invalid:
        alert('refresh token is dead, log in again')
    else:
        retry_later()
```

RFC 6749 §5.2 defines `invalid_grant` for exactly this case, so the signal is
a standard one. Schwab does not put it where the standard says. It answers
with an outer code of `unsupported_token_type` -- which RFC 7009 defines for
the *revocation* endpoint and which describes nothing that happened -- and
nests the real response as a JSON string inside the description:

```
unsupported_token_type: 400 Bad Request: {"error_description":"Refresh token
is invalid, expired or revoked","error":"invalid_grant"}
```

Observed on a live account on 2026-08-02, by letting a refresh token reach its
seven day expiry deliberately. Schwab documents neither the response nor the
nesting, so that is one account on one day rather than a specification. Both
placements are accepted, in case the outer code is ever corrected.

Anything unrecognized returns `False`. An application stopped by a failure it
could have retried through is worse off than one which retried a little too
long, so the unrecognized case falls on the transient side.

Offered upstream as #266.

### Notes

1.10.0's documentation said this library would not tell you whether a retry
could succeed, because Schwab documents the seven day term but not the
response. That was true of the documentation and remains true; it was not true
that nobody had seen the response. This corrects it.

## 1.10.0

The rest of the production audit -- the findings which were real but not
urgent, plus the one piece of design it turned up.

One behaviour change worth reading before upgrading: a rejected token refresh
now raises a schwab-py exception rather than an authlib one.

### Added

**`TokenRefreshError`, so a failed refresh has a type of ours.** The session
refreshes the token on the way past an ordinary request, so a refusal by
Schwab surfaced from `get_quote` as
`authlib.integrations.base_client.errors.OAuthError` -- a type this library
never mentioned, from a package the user did not choose to depend on. Measured
across the failure spectrum, callers were catching three different third-party
types and none of them ours.

`schwab.utils.TokenRefreshError` now wraps it, keeping the original as
`__cause__` and carrying the token's age:

```python
from schwab.utils import TokenRefreshError

try:
    r = c.get_quote('AAPL')
except TokenRefreshError as e:
    if e.token_age is not None and e.token_age > 7 * 24 * 60 * 60:
        alert('token past its seven day window, log in again')
    else:
        retry_later()
```

It deliberately does **not** classify the failure as terminal or transient.
Schwab documents the seven day refresh token term but not what the token
endpoint returns when that term expires, so a classifier keyed on error codes
would be built on a payload shape nobody has seen. The age is documented; the
error code is not. Offered upstream as #263.

**`Client.close_session()`.** `AsyncClient` could always be closed and the
synchronous client could not, so an application creating clients repeatedly
held their connections until each session happened to be garbage collected.
Both are now documented, which neither was. Offered upstream as #265.

### Fixed

**Temporary token files left behind by a hard kill are now swept.** The
cleanup on the exception path never runs for a `SIGKILL`, and what a killed
write leaves behind is not an empty file -- it is a complete, readable copy of
the token. Measured: 25 processes killed inside the write window left 12 of
them, and nothing ever removed them. A refresh token stays valid for the rest
of its seven days, so a process which crash-loops accumulates live credentials
next to its token file. Each subsequent write now removes any it finds, but
only files matching this library's own temporary name, and only once they are
a minute old -- another process may be partway through its own write, and
deleting its temporary file would break it. Added to #232, which introduced
the temporary file.

**The wait for the login callback server is bounded, and checks what
answered.** A server which started but never answered left
`client_from_login_flow` spinning with nothing on screen to say why; it was
still going when killed at 12 seconds. Worse, the status check's response was
assigned and never read, so *any* listener on that port counted as the
callback server -- and continuing hands it the login redirect, which carries an
authorization code good enough to take over the account. A non-200 now refuses
the flow. Interactive path only. Offered upstream as #264.

### Documentation

`client_from_access_functions` said "Please see this example for details"
about the exact signatures a custom token-storage function must have, and
linked to a file which returns 404 in this fork and upstream. The one place
the signatures were explained was the one place that was not there. They are
now written out inline, where they cannot rot the same way.

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
