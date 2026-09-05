``schwaby``
===========

**A Python client for the Charles Schwab API, built for code that trades real
money.**

.. image:: https://github.com/Hu1kSmash/schwaby/workflows/tests/badge.svg
  :target: https://github.com/Hu1kSmash/schwaby/actions?query=workflow%3Atests

Every endpoint Schwab publishes. A streaming websocket that returns
``{'ASK_PRICE': 421.60}`` instead of ``{'2': 421.60}``. Orders assembled from
named parts rather than hand-built JSON. Synchronous and ``asyncio`` over the
same interface.

And underneath it, the guarantees you want when the account is funded: a price
that arrives exactly as you wrote it, a token file that survives a crash, and a
stream that tells you what it swallowed instead of going quiet.

.. code-block:: shell

  pip install schwaby

That is the whole install. Python 3.10 and up, no extras to remember.

Sixty seconds in
----------------

**Authenticate once.** A browser opens, you log in, and the token is written to
disk and refreshed for you from then on.

.. code-block:: python

  from schwab.auth import easy_client

  c = easy_client(
          api_key='YOUR_API_KEY',
          app_secret='YOUR_APP_SECRET',
          callback_url='https://127.0.0.1:8182',
          token_path='/path/to/token.json')

**Ask for data.** You get back the raw ``httpx2`` response, so nothing is
guessed at on your behalf.

.. code-block:: python

  r = c.get_price_history_every_day('AAPL')
  r.raise_for_status()
  candles = r.json()['candles']

**Place an order** from a template, without touching Schwab's order JSON.

.. code-block:: python

  from schwab.orders.equities import equity_buy_limit

  account_hash = c.get_account_numbers().json()[0]['hashValue']
  c.place_order(account_hash, equity_buy_limit('AAPL', 10, '210.50'))

Note the price is a **string**. ``schwaby`` refuses a ``float`` here, and the
section below explains why that is a feature.

**Stream quotes**, with fields you can read.

.. code-block:: python

  import asyncio
  from schwab.streaming import StreamClient

  async def main():
      stream = StreamClient(c)
      await stream.login()

      stream.add_level_one_equity_handler(
              lambda msg: print(msg['content'][0]['ASK_PRICE']))
      await stream.level_one_equity_subs(['AAPL', 'MSFT'])

      while True:
          await stream.handle_message()

  asyncio.run(main())

Ready to start? The `getting started guide
<https://github.com/Hu1kSmash/schwaby/blob/main/docs/getting-started.rst>`__
walks through registering an app with Schwab and getting your first token, and
the `documentation
<https://github.com/Hu1kSmash/schwaby/blob/main/docs/index.rst>`__ covers the
rest.

What it covers
--------------

* **Authentication** --- browser login, a manual flow for headless boxes and
  notebooks, a two-step flow for web backends, and token refresh handled for
  you.
* **Market data** --- quotes, fundamentals, option chains, price history at
  seven granularities, movers, market hours, instrument lookup.
* **Streaming** --- thirteen real-time services over one websocket: level one
  equities, options, futures and forex, order book depth from Nasdaq and NYSE,
  chart and screener feeds, and your own account activity.
* **Orders** --- construction, placement, replacement, cancellation and
  preview, with ready-made templates for the common equity orders and option
  strategies.
* **Accounts** --- balances, positions, orders and transaction history.
* **Sync and async** --- swap ``Client`` for ``AsyncClient``, add ``await``,
  change nothing else.

Why this one
------------

Schwab's API is capable, and a few corners of it are unforgiving. These are the
ones ``schwaby`` takes on, and what each costs you when it is missing.

**Your prices arrive exactly as you wrote them.** ``set_price`` takes a string
or a ``decimal.Decimal`` and refuses a ``float``, because a float cannot
represent most prices exactly and converting one has to round somewhere.
``8.2 * 100`` is ``819.9999999999999``; truncate that and you have sent an order
a cent low, with nothing anywhere to say so. Making the caller decide the
rounding is the only version of this that cannot be silently wrong.

**A token file that survives a crash.** Token writes go to a temporary file and
are renamed into place, so a process killed mid-refresh leaves either the old
token or the new one --- never a half-written file that can only be repaired by
sitting down at a browser. ``client.token_age()`` tells you how long you have
before Schwab's seven-day refresh window closes, counted from the original
authorization rather than the last refresh, which is the number that actually
governs expiry.

**A stream that says what it swallowed.** A websocket client has to absorb some
failures: a handler that raised, a response to a request nobody is waiting for
any more, a frame that will not parse. Absorbing them quietly makes a broken
feed look like a slow one. ``add_error_handler`` hands you every one of them as
an exception object, so a stalled strategy can tell the difference between a
quiet market and a stream that stopped working an hour ago.

**Readable messages instead of numbered fields.** Schwab's streamer identifies
every field by number, and the same number means different things on different
services --- field ``2`` is the ask price on ``LEVELONE_EQUITIES`` and the open
price on ``CHART_EQUITY``. ``schwaby`` carries the field tables for all thirteen
services and relabels each message as it arrives. It also handles login and
logout, matches each response to its request, and lets you register a handler
per service instead of demultiplexing the stream yourself.

**Orders Schwab will accept.** Order JSON is deeply nested, and a malformed
order comes back rejected with little hint as to what was wrong.
``OrderBuilder`` assembles it from named parts and validates what it can, while
``schwab.orders.equities`` and ``schwab.orders.options`` provide templates for
the orders and option strategies most people actually place.

**Enums, not magic strings.** Every endpoint's legal parameter values are enums
on the client, so a misspelled projection or an invalid order duration fails
immediately in Python rather than arriving as an opaque HTTP 400 halfway
through a session.

**Thin everywhere else.** Outside those corners this library gets out of the
way. It takes raw values and hands back the raw ``httpx2`` response for you to
interpret. Anything you can do with raw HTTP you can do here, only more easily.

The documentation is worth reading even if you end up calling the API directly.
Schwab's developer portal is behind a login, so for much of this API these pages
are the most accessible description of how it actually behaves.

Installing
----------

.. code-block:: shell

  pip install schwaby

**The distribution is** ``schwaby``\ **. The importable package is**
``schwab``\ **.** Those differ on purpose: keeping the import makes this a
drop-in replacement, so moving an existing project over is one line of
``requirements.txt``.

.. code-block:: python

  import schwab

.. warning::

  **Do not install** ``schwaby`` **alongside** ``schwab-py``\ **.** Both provide
  the ``schwab`` package, so whichever lands second silently overwrites the
  other's files. ``pip`` gives no warning, nothing fails at install time, and
  the first sign of trouble is behaviour from a version you did not choose.
  Uninstall one before installing the other.

What it does not do
-------------------

A few things people ask for that Schwab's API does not offer:

* **No paper trading.** Orders placed through this API are real.
* **No historical options pricing.** Current chains only.
* **No thinkorswim.** Schwab owns `thinkorswim
  <https://www.schwab.com/trading/thinkorswim/desktop>`__, but this API is
  unaffiliated with it. You can trade the same accounts; some of what TOS does
  has no API equivalent.

Getting help and contributing
-----------------------------

Bug reports, questions, suggestions and patches all go to the repository: open
an `issue <https://github.com/Hu1kSmash/schwaby/issues>`__ or a `pull request
<https://github.com/Hu1kSmash/schwaby/pulls>`__.

If you have found something that also affects `alexgolec/schwab-py
<https://github.com/alexgolec/schwab-py>`__ and is not one of the changes listed
in the `changelog
<https://github.com/Hu1kSmash/schwaby/blob/main/CHANGELOG.md>`__, it is worth
reporting there as well. It will help more people than a report here alone.

Where this came from
--------------------

``schwaby`` began from `alexgolec/schwab-py
<https://github.com/alexgolec/schwab-py>`__, an excellent MIT-licensed library by
Alex Golec that gave this project its shape --- the endpoint coverage, the order
builder, the streaming field tables. He wrote the great majority of the code
here, and his copyright and licence are unchanged.

It became a separate project for a practical reason rather than a philosophical
one. This client runs systematic strategies against funded accounts, and that
use imposes requirements a general-purpose wrapper has no particular reason to
prioritise: the four guarantees above, most of which needed changes to existing
behaviour rather than additions on top of it.

Those changes were offered upstream first. They were not taken up, so rather
than run an ever-growing private patch set against someone else's release
schedule, they were consolidated here and this became its own project with its
own release line.

License
-------

``schwaby`` is released under the `MIT license
<https://github.com/Hu1kSmash/schwaby/blob/main/LICENSE>`__, and remains
copyright Alex Golec.

**Disclaimer:** *schwaby is an unofficial API wrapper. It is in no way endorsed
by or affiliated with Charles Schwab or any associated organization. Make sure
to read and understand the terms of service of the underlying API before using
this package. The authors accept no responsibility for any damage that might
stem from use of this package. See the LICENSE file for more details.*
