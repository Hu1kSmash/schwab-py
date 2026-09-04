# Changelog

This is a maintained fork of [`alexgolec/schwab-py`](https://github.com/alexgolec/schwab-py).
Versions below 1.6.0 are upstream releases; see the upstream repository for their notes.

Every change in this fork is offered upstream as a pull request, so that where upstream merges
one, the fork's divergence shrinks accordingly.

Two changes are currently exceptions. Both were branched from this fork's `main` rather than
from a mirror of upstream, so their diffs carry the version bump, the changed URLs and this
notice along with the actual change, which makes them unreviewable as pull requests:

- the streaming client's response-routing model, introduced in 1.7.0;
- the move to `httpx2` and Authlib 1.8, released in 2.0.0. This one was branched from `main`
  deliberately, because upstream's `auth.py` still carries only the bare `except
  httpx.ConnectError` and the migration rewrites that exact line. Re-cutting it against
  `upstream-main` would mean porting it without the ConnectTimeout sibling fix.

Separating both out is outstanding work. They are called out here rather than left to be
inferred from the pull request list.

---

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
