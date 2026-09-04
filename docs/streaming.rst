.. highlight:: python
.. py:module:: schwab.streaming

.. _stream:


================
Streaming Client
================

A wrapper around the Schwab streaming data API.  This API is a websockets-based 
streaming API that provides to up-to-the-second data on market activity. Most 
impressively, it provides realtime data, including Level Two and time of sale 
data for major equities, options, and futures exchanges. 

Here's an example of how you can receive book snapshots of ``GOOG`` (note if you 
run this outside regular trading hours you may not see anything):

.. code-block:: python

  from schwab.auth import easy_client
  from schwab.client import Client
  from schwab.streaming import StreamClient

  import asyncio
  import json

  # Assumes you've already created a token. See the authentication page for more
  # information.
  client = easy_client(
          api_key='YOUR_API_KEY',
          app_secret='YOUR_APP_SECRET',
          callback_url='https://127.0.0.1',
          token_path='/path/to/token.json')
  stream_client = StreamClient(client, account_id=1234567890)

  async def read_stream():
      await stream_client.login()
 
      def print_message(message):
        print(json.dumps(message, indent=4))

      # Always add handlers before subscribing because many streams start sending 
      # data immediately after success, and messages with no handlers are dropped.
      stream_client.add_nasdaq_book_handler(print_message)
      await stream_client.nasdaq_book_subs(['GOOG'])

      while True:
          await stream_client.handle_message()

  asyncio.run(read_stream())


++++++++++++
Use Overview
++++++++++++

The example above demonstrates the end-to-end workflow for using ``schwab.stream``. 
There's more in there than meets the eye, so let's dive into the details.


----------
Logging In
----------

Before we can perform any stream operations, the client must be logged in to the 
stream. Unlike the HTTP client, in which every request is authenticated using a 
token, this client sends unauthenticated requests and instead authenticates the 
entire stream. As a result, this login process is distinct from the token 
generation step that's used in the HTTP client.

Stream login is accomplished simply by calling :meth:`StreamClient.login()`. Once
this happens successfully, all stream operations can be performed. Attemping to
perform operations that require login before this function is called raises an
exception.

.. automethod:: schwab.streaming.StreamClient.login

Requests to the streaming server -- logging in, subscribing, logging out -- give
up after ``response_timeout`` seconds if the server accepts the request but
never answers it, raising
:class:`~schwab.streaming.ResponseTimeoutError`. It defaults to 60 seconds and
can be set per client:

.. code-block:: python

  stream_client = StreamClient(client, response_timeout=30.0)

Pass ``None`` to wait indefinitely. Note that the websockets keepalive does not
cover this case: a connection which is alive but simply not answering keeps
replying to pings, so without a timeout such a request would wait forever.


-----------------------
Logging Out and Closing
-----------------------

For a clean exit, it's recommended to log out of the stream when you're done.
This sends a logout request and then closes the connection.

.. automethod:: schwab.streaming.StreamClient.logout

If the connection has already failed, or you are tearing a client down without
ceremony, :meth:`close` skips the logout and just closes the socket. It is safe
to call more than once, and safe on a client which was never logged in.

.. automethod:: schwab.streaming.StreamClient.close

The client is also an async context manager, which closes it on the way out:

.. code-block:: python

  async with StreamClient(client) as stream_client:
      await stream_client.login()
      ...

Closing matters more than it might appear. A client which is never closed leaves
its socket and keepalive task alive until the object is collected, which for a
long-running process means until it exits -- typically leaving the connection to
be finalized during interpreter shutdown, when the event loop may already be
gone.


----------------------
Subscribing to Streams
----------------------

These functions have names that follow the pattern ``SERVICE_NAME_subs``. These
functions send a request to enable streaming data for a particular data stream.
They are *not* thread safe, so they should only be called from one thread.

They can, however, be called while another coroutine is waiting in
``handle_message()``. One request is in flight at a time, and whichever coroutine
is reading the socket hands the response to whoever is waiting for it, so a
subscription made against a quiet stream is sent immediately rather than waiting
for a message to arrive first.

When subscriptions are called multiple times on the same stream, the results 
vary. What's more, these results aren't documented in the official 
documentation. As a result, it's recommended not to call a subscription function 
more than once for any given stream.

Some services, notably :ref:`equity_charts` and :ref:`futures_charts`, 
offer ``SERVICE_NAME_add`` functions which can be used to add symbols to the 
stream after the subscription has been created. For others, calling the 
subscription methods again seems to clear the old subscription and create a new 
one. Note this behavior is not officially documented, so this interpretation may 
be incorrect.


----------------------
Add symbols to Streams
----------------------

These functions have names that follow the pattern ``SERVICE_NAME_add``.
These functions send a request to add to the list of subscribed symbols for a
particular data stream.


-------------------------
Un-Subscribing to Streams
-------------------------

These functions have names that follow the pattern ``SERVICE_NAME_unsubs``.
These functions send a request to disable the symbols of a streaming data for a
particular data stream. They are *not* thread safe, so they should only be
called from one thread. When unsubscribing to services with symbols, symbols
which were not explicitly unsubscribed remain subscribed.


--------------------
Registering Handlers
--------------------

By themselves, the subscription functions outlined above do nothing except cause 
messages to be sent to the client. The ``add_SERVICE_NAME_handler`` functions 
register functions that will receive these messages when they arrive. When 
messages arrive, these handlers will be called serially. There is no limit to 
the number of handlers that can be registered to a service.


.. _registering_handlers:

-----------------
Handling Messages
-----------------

Once the stream client is properly logged in, subscribed to streams, and has 
handlers registered, we can start handling messages. This is done simply by 
awaiting on the ``handle_message()`` function. This function reads a single 
message and dispatches it to the appropriate handler or handlers.

If a message is received for which no handler is registered, that message is
ignored.

A handler which raises does not stop the others from seeing the message, and
does not propagate out of ``handle_message()`` into your receive loop, where it
would be indistinguishable from the connection failing. The failure is reported
on the ``schwab.streaming`` logger instead, with the service name attached. This
applies equally to synchronous and coroutine handlers.

That is worth knowing when debugging: **a handler which is quietly failing shows
up in the logs and nowhere else** -- unless you ask for it. See
:ref:`error_handlers` below. If you are relying on a handler to do something
important, do one or the other. See :ref:`enable_logging <help>` for how to turn
logging on.

Handlers should take a single argument representing the stream message received:

.. code-block:: python

  import json

  def sample_handler(msg):
      print(json.dumps(msg, indent=4))


.. _error_handlers:

------------------------------
Reacting to Absorbed Failures
------------------------------

Skipping a failed handler is the right behaviour, but it leaves you with a log
record rather than something you can act on. If your program needs to *react* --
raise an alert, increment a counter, mark a subscription unhealthy -- register
an error handler:

.. code-block:: python

  def on_stream_error(service, exception, message):
      alert('schwab stream: %s raised %r' % (service, exception))

  stream_client.add_error_handler(on_stream_error)

It is called for two things: a stream handler which raised, and a connection
which failed to close after logout. ``service`` and ``message`` are ``None``
where they do not apply. Registering none keeps the existing behaviour exactly,
and the log line is written either way.

This matters most when something else covers for the stream. If a subscription
quietly stops delivering and a REST poll is authoritative anyway, nothing looks
wrong until something the poll does not cover finally breaks. **A silent failure
that a fallback hides is the one most worth having a signal for.**

An error handler is called for effect; its return value is ignored, and if it
raises, that is logged and swallowed. A callback for absorbed failures must not
itself become a way to fail.

.. automethod:: schwab.streaming.StreamClient.add_error_handler

---------------------
Data Field Relabeling
---------------------

Under the hood, this API returns JSON objects with numerical key representing
labels: 

.. code-block:: python

  {
    "service": "CHART_EQUITY",
    "timestamp": 1715908546054,
    "command": "SUBS",
    "content": [{
          "seq": 0,
          "key": "MSFT",
          "1": 779,
          "2": 421.65,
          "3": 421.79,
          "4": 421.65,
          "5": 421.755,
          "6": 26.0,
          "7": 1715903940000,
          "8": 19859
      }]
  }

These labels are tricky to decode, and require a knowledge of the documentation 
to decode properly. ``schwab-api`` makes your life easier by doing this decoding 
for you, replacing numerical labels with strings proposed by the community For 
instance, the message above would be relabeled as:

.. code-block:: python

  {
    "service": "CHART_EQUITY",
    "timestamp": 1715908546054,
    "command": "SUBS",
    "content": [{
          "seq": 0,
          "key": "MSFT",
          "SEQUENCE": 779,
          "OPEN_PRICE": 421.65,
          "HIGH_PRICE": 421.79,
          "LOW_PRICE": 421.65,
          "CLOSE_PRICE": 421.755,
          "VOLUME": 26.0,
          "CHART_TIME_MILLIS": 1715903940000,
          "CHART_DAY": 19859
      }]
  }

This documentation describes the various fields and their numerical values. You 
can find them by investigating the various enum classes ending in ``***Fields``.

.. warning::

   **Relabeling is not applied uniformly.** Schwab delivers messages on two
   channels. Content arriving on the ``data`` channel is relabeled as above.
   Content arriving on the ``notify`` channel is passed to your handler
   **unchanged**, with its bare numeric field ids intact.

   Both reach the same handlers, so a handler which assumes relabeling will
   mis-parse a notify frame -- and it will do so by finding nothing rather than
   by raising, since the keys it looks for are simply absent. If you read fields
   by name, check they are present rather than assuming them.

   This is a property of the library, not of Schwab's protocol.

Some streams, such as the ones described in :ref:`level_one`, allow you to
specify a subset of fields to be returned. Subscription handlers for these
services take a list of the appropriate field enums the extra ``fields``
parameter. If nothing is passed to this parameter, all supported fields are 
requested.


---------------
Stream Statuses
---------------

Schwab's streaming functionality is closely modelled on that of the former 
TDAmeritrade API, and this module was adapted from an implementation written 
against it.

As a result, some streams may have been carried over which don't actually work. 
Some never worked at all, and were implemented only because now-defunct 
documentation referred to them.

The community is in the process of making sense of this new world. You are 
encouraged to try and use this streaming library and report what you find back 
`on the issue tracker <https://github.com/Hu1kSmash/schwab-py/issues>`__. We'll be updating 
this page as we discover new things.

The following streams are confirmed working:
 * :ref:`charts`
 * :ref:`level_one`
 * :ref:`level_two`
 * :ref:`screener`
 * :ref:`account_activity`


.. _charts:

++++++++++++
OHLCV Charts
++++++++++++

These streams summarize trading activity on a minute-by-minute basis for 
equities and futures, providing OHLCV (Open/High/Low/Close/Volume) data.


.. _equity_charts:

-------------
Equity Charts
-------------

Minute-by-minute OHLCV data for equities.

.. automethod:: schwab.streaming::StreamClient.chart_equity_subs
.. automethod:: schwab.streaming::StreamClient.chart_equity_unsubs
.. automethod:: schwab.streaming::StreamClient.chart_equity_add
.. automethod:: schwab.streaming::StreamClient.add_chart_equity_handler
.. autoclass:: schwab.streaming::StreamClient.ChartEquityFields
  :members:
  :undoc-members:


.. _futures_charts:

--------------
Futures Charts
--------------

Minute-by-minute OHLCV data for futures.

.. automethod:: schwab.streaming::StreamClient.chart_futures_subs
.. automethod:: schwab.streaming::StreamClient.chart_futures_unsubs
.. automethod:: schwab.streaming::StreamClient.chart_futures_add
.. automethod:: schwab.streaming::StreamClient.add_chart_futures_handler
.. autoclass:: schwab.streaming::StreamClient.ChartFuturesFields
  :members:
  :undoc-members:


.. _level_one:

++++++++++++++++
Level One Quotes
++++++++++++++++

Level one quotes provide an up-to-date view of bid/ask/volume data. In 
particular they list the best available bid and ask prices, together with the 
requested volume of each. They are updated live as market conditions change.


.. _level_one_quotes_stream:

---------------
Equities Quotes
---------------

Level one quotes for equities traded on NYSE, AMEX, and PACIFIC.

.. automethod:: schwab.streaming::StreamClient.level_one_equity_subs
.. automethod:: schwab.streaming::StreamClient.level_one_equity_unsubs
.. automethod:: schwab.streaming::StreamClient.level_one_equity_add
.. automethod:: schwab.streaming::StreamClient.add_level_one_equity_handler
.. autoclass:: schwab.streaming::StreamClient.LevelOneEquityFields
  :members:
  :undoc-members:


.. _level_one_option_stream:

--------------
Options Quotes
--------------

Level one quotes for options. Note you can use 
:meth:`Client.get_option_chain() <schwab.client.Client.get_option_chain>` to fetch
available option symbols.

.. automethod:: schwab.streaming::StreamClient.level_one_option_subs
.. automethod:: schwab.streaming::StreamClient.level_one_option_unsubs
.. automethod:: schwab.streaming::StreamClient.level_one_option_add
.. automethod:: schwab.streaming::StreamClient.add_level_one_option_handler
.. autoclass:: schwab.streaming::StreamClient.LevelOneOptionFields
  :members:
  :undoc-members:


.. _level_one_futures_stream:

--------------
Futures Quotes
--------------

Level one quotes for futures.

.. automethod:: schwab.streaming::StreamClient.level_one_futures_subs
.. automethod:: schwab.streaming::StreamClient.level_one_futures_unsubs
.. automethod:: schwab.streaming::StreamClient.level_one_futures_add
.. automethod:: schwab.streaming::StreamClient.add_level_one_futures_handler
.. autoclass:: schwab.streaming::StreamClient.LevelOneFuturesFields
  :members:
  :undoc-members:


.. _level_one_futures_options_stream:

----------------------
Futures Options Quotes
----------------------

Level one quotes for futures options.

.. automethod:: schwab.streaming::StreamClient.level_one_futures_options_subs
.. automethod:: schwab.streaming::StreamClient.level_one_futures_options_unsubs
.. automethod:: schwab.streaming::StreamClient.level_one_futures_options_add
.. automethod:: schwab.streaming::StreamClient.add_level_one_futures_options_handler
.. autoclass:: schwab.streaming::StreamClient.LevelOneFuturesOptionsFields
  :members:
  :undoc-members:


.. _level_one_forex_stream:

------------
Forex Quotes
------------

Level one quotes for foreign exchange pairs.

.. automethod:: schwab.streaming::StreamClient.level_one_forex_subs
.. automethod:: schwab.streaming::StreamClient.level_one_forex_unsubs
.. automethod:: schwab.streaming::StreamClient.level_one_forex_add
.. automethod:: schwab.streaming::StreamClient.add_level_one_forex_handler
.. autoclass:: schwab.streaming::StreamClient.LevelOneForexFields
  :members:
  :undoc-members:


.. _level_two:

++++++++++++++++++++
Level Two Order Book 
++++++++++++++++++++

Level two streams provide a view on continuous order books of various securities.
The level two order book describes the current bids and asks on the market, and 
these streams provide snapshots of that state.

Due to the lack of official documentation, these streams are largely reverse 
engineered.  While the labeled data represents a best effort attempt to
interpret stream fields, it's possible that something is wrong or incorrectly
labeled.

The documentation lists more book types than are implemented here. In 
particular, it also lists ``FOREX_BOOK``, ``FUTURES_BOOK``, and
``FUTURES_OPTIONS_BOOK`` as accessible streams. All experimentation has resulted 
in these streams refusing to connect, typically returning errors about 
unavailable services. Due to this behavior and the lack of official 
documentation for book streams generally, ``schwab-api`` assumes these streams are not
actually implemented, and so excludes them. If you have any insight into using
them, please `let us know <https://github.com/Hu1kSmash/schwab-py/issues>`__.


-------------------------------------
Equities Order Books: NYSE and NASDAQ
-------------------------------------

``schwab-api`` supports level two data for NYSE and NASDAQ, which are the two major 
exchanges dealing in equities, ETFs, etc. Stocks are typically listed on one or 
the other, and it is useful to learn about the differences between them:

 * `"The NYSE and NASDAQ: How They Work" on Investopedia
   <https://www.investopedia.com/articles/basics/03/103103.asp>`__
 * `"Here's the difference between the NASDAQ and NYSE" on Business Insider
   <https://www.businessinsider.com/
   heres-the-difference-between-the-nasdaq-and-nyse-2017-7>`__
 * `"Can Stocks Be Traded on More Than One Exchange?" on Investopedia
   <https://www.investopedia.com/ask/answers/05/stockmultipleexchanges.asp>`__

You can identify on which exchange a symbol is listed by using
:meth:`Client.search_instruments() <schwab.client.Client.search_instruments>`:

.. code-block:: python

  r = c.search_instruments(['GOOG'], projection=c.Instrument.Projection.FUNDAMENTAL)
  assert r.status_code == httpx2.codes.OK, r.raise_for_status()
  print(r.json()['GOOG']['exchange'])  # Outputs NASDAQ

However, many symbols have order books available on these streams even though 
this API call returns neither NYSE nor NASDAQ. The only sure-fire way to find out
whether the order book is available is to attempt to subscribe and see what 
happens.

Note to preserve equivalence with what little documentation there is, the NYSE
book is called "listed." Testing indicates this stream corresponds to the NYSE
book, but if you find any behavior that suggests otherwise please
`let us know <https://github.com/Hu1kSmash/schwab-py/issues>`__.

.. automethod:: schwab.streaming::StreamClient.nyse_book_subs
.. automethod:: schwab.streaming::StreamClient.nyse_book_unsubs
.. automethod:: schwab.streaming::StreamClient.nyse_book_add
.. automethod:: schwab.streaming::StreamClient.add_nyse_book_handler

.. automethod:: schwab.streaming::StreamClient.nasdaq_book_subs
.. automethod:: schwab.streaming::StreamClient.nasdaq_book_unsubs
.. automethod:: schwab.streaming::StreamClient.nasdaq_book_add
.. automethod:: schwab.streaming::StreamClient.add_nasdaq_book_handler


------------------
Options Order Book
------------------

This stream provides the order book for options. It's not entirely clear what 
exchange it aggregates from, but it's been tested to work and deliver data. The 
leading hypothesis is that it is the order book for the 
`Chicago Board of Exchange <https://www.cboe.com/us/options>`__ options 
exchanges, although this is an admittedly an uneducated guess.

.. automethod:: schwab.streaming::StreamClient.options_book_subs
.. automethod:: schwab.streaming::StreamClient.options_book_unsubs
.. automethod:: schwab.streaming::StreamClient.options_book_add
.. automethod:: schwab.streaming::StreamClient.add_options_book_handler


.. _screener:

++++++++
Screener
++++++++

Top 10 advances and decliners by volume, trades, percent change and average percent
volume.

Symbols in upper case and separated by commas.

(PREFIX)_(SORTFIELD)_(FREQUENCY) where PREFIX is:
 * Indices: $COMPX $DJI, $SPX.X, INDEX_ALL
 * Exchanges: NYSE, NASDAQ, OTCBB, EQUITY_ALL
 * Option: OPTION_PUT, OPTION_CALL, OPTION_ALL

and sortField is:
 * VOLUME, TRADES, PERCENT_CHANGE_UP, PERCENT_CHANGE_DOWN, AVERAGE_PERCENT_VOLUME

and frequency is:
 * 0, 1, 5, 10, 30 60 minutes (0 is for all day)

Both the equity and option screener streams use a common set of fields:

.. autoclass:: schwab.streaming::StreamClient.ScreenerFields
  :members:
  :undoc-members:


---------------
Screener Equity
---------------

.. automethod:: schwab.streaming::StreamClient.screener_equity_subs
.. automethod:: schwab.streaming::StreamClient.screener_equity_unsubs
.. automethod:: schwab.streaming::StreamClient.screener_equity_add
.. automethod:: schwab.streaming::StreamClient.add_screener_equity_handler


---------------
Screener Option
---------------

.. automethod:: schwab.streaming::StreamClient.screener_option_subs
.. automethod:: schwab.streaming::StreamClient.screener_option_unsubs
.. automethod:: schwab.streaming::StreamClient.screener_option_add
.. automethod:: schwab.streaming::StreamClient.add_screener_option_handler


.. _account_activity:

++++++++++++++++
Account Activity
++++++++++++++++

.. automethod:: schwab.streaming::StreamClient.account_activity_sub
.. automethod:: schwab.streaming::StreamClient.account_activity_unsubs
.. automethod:: schwab.streaming::StreamClient.add_account_activity_handler
.. autoclass:: schwab.streaming::StreamClient.AccountActivityFields
  :members:
  :undoc-members:

----------------------------------------
What the payload looks like, as observed
----------------------------------------

The three fields above are relabeled for you. What is *inside* ``MESSAGE_DATA``
is not documented by Schwab, so every consumer ends up reverse-engineering it
and keeping the results privately.

What follows was contributed from roughly a year of one fleet's production
traffic on funded accounts. **It is an observation log, not a contract.** Schwab
publishes none of this, nothing here is validated by this library, and a shape
that never appeared in that fleet's traffic is not thereby impossible. Treat it
as a map drawn by someone who has been there, not as a specification.

**The order identifier appears under at least seven spellings**, and which one
you get depends on the message:

.. code-block:: python

  ('SchwabOrderID', 'schwabOrderID', 'OrderID', 'orderId',
   'OrderKey', 'orderKey', 'order_id')

**The symbol appears under four**, in descending order of preference:

.. code-block:: python

  ('Symbol', 'symbol', 'PrimaryMarketSymbol', 'UnderlyingSymbol')

``Symbol`` is the tradeable ticker, and is an OCC option string for an option
leg. The other two are fallbacks for shapes that carry only those.

**Statuses observed to be terminal**:

.. code-block:: python

  ('FILLED', 'REJECTED', 'CANCELED', 'EXPIRED', 'REPLACED')

Note ``CANCELED`` with one L.

**``MESSAGE_TYPE`` tokens observed**:

.. code-block:: python

  ('SUBSCRIBED', 'ORDERCREATED', 'ORDERACCEPTED',
   'EXECUTIONREQUESTED', 'EXECUTIONREQUESTCREATED',
   'EXECUTIONREQUESTCOMPLETED', 'ORDERFILLCOMPLETED',
   'ORDERPARTIALFILL', 'ORDERPARTIALLYFILLED', 'ORDERREJECTED',
   'ORDERCANCELED', 'ORDERCANCELLED', 'ORDERUROUT', 'ORDEREXPIRED',
   'ORDERREPLACED')

Both ``CANCELED`` and ``CANCELLED`` appear -- the spelling is not consistent
within Schwab's own tokens, so match on both. ``ORDERUROUT`` is Schwab's
spelling for an unsolicited out.

**Distinguishing a relabeled item from a raw one.** After relabeling, a
``data``-channel content item carries ``seq``, ``key``, ``ACCOUNT``,
``MESSAGE_TYPE`` and ``MESSAGE_DATA``. A content item carrying none of those is
a ``notify``-channel item, which this library forwards unchanged -- see the
warning under :ref:`Data Field Relabeling <stream>` above. Observed values there
include an activity token of ``orderfill`` and a benign notice reading
``feature not supported``.

If you learn something this list gets wrong, a pull request correcting it is
more useful than a private patch.
