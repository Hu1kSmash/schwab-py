# Security Policy

This library holds OAuth credentials for brokerage accounts and can place
trades. Please treat problems in it accordingly.

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Use [private vulnerability
reporting](https://github.com/Hu1kSmash/schwab-py/security/advisories/new),
which opens a report only the maintainers can see.

Please include what an attacker would be able to do, how to reproduce it, and
which version you were on. If it affects the original project too, say so — it
should be reported [there](https://github.com/alexgolec/schwab-py/security)
as well, since most users are on that one.

## Supported versions

The most recent release. This is a small project; there are no backports.

## What is in scope

Anything which could expose a token, an app secret, an account number or an
account hash, or which could cause an order to be placed, modified or cancelled
other than as the caller asked. Examples of the kinds of thing that count:

- credentials written somewhere readable by other users, or left recoverable
- secrets reaching logs, exception messages or tracebacks unredacted
- an order built or sent with values the caller did not specify

The last one is not hypothetical. Version 1.7.0 fixed response redaction never
running, and 1.6.0 fixed prices silently coming out a cent low.

## What is not in scope

- Schwab's own API, its authentication or its rate limits — report those to
  Schwab
- Anything requiring an attacker to already have your token file
- Losing money on a trade the library placed exactly as instructed

## Handling your token

For what it is worth, since most reports in this area turn out to be
configuration rather than defects:

- the token file is written `0600`, and is a credential in its own right
- never commit it, never paste it into an issue, and never share it in logs
- `enable_bug_report_logging()` makes a best effort to redact logs, and its own
  documentation is explicit that this is best effort — read what you are about
  to post
