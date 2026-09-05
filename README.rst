``schwaby``: A Charles Schwab API Client for Systematic Trading
===============================================================

``schwaby`` is an unofficial Python client for the Charles Schwab API, built for
running automated strategies against real accounts.

.. note::

   **Where this came from.** ``schwaby`` began from
   `alexgolec/schwab-py <https://github.com/alexgolec/schwab-py>`__, an excellent
   MIT-licensed library by Alex Golec that gave this project its shape --- the endpoint
   coverage, the order builder, the streaming field tables. He wrote the great majority of
   the code here and his copyright and licence are unchanged.

   It became a separate project for a practical reason rather than a philosophical one. This
   client runs systematic strategies against funded accounts, and that use imposes
   requirements a general-purpose wrapper has no particular reason to prioritise: prices that
   are never silently altered, a token file that survives a crash mid-refresh, a stream that
   reports what it absorbs instead of going quiet, and failures that are loud and specific
   rather than plausible-looking. Several of those needed changes to behaviour rather than
   additions on top.

   Those changes were offered upstream first. They were not taken up, so rather than run an
   ever-growing private patch set against someone else's release schedule, they were
   consolidated here and this became its own project with its own release line.

   **The distribution is** ``schwaby``\ **; the importable package is still** ``schwab``.

   The first PyPI release is not out yet. Until it is, install from ``main``:

   .. code-block:: shell

     pip install "schwaby[login] @ git+https://github.com/Hu1kSmash/schwaby@main"

   Note that must be ``@main`` rather than a tag: every tag so far was published
   under the old distribution name, and ``pip`` refuses a direct URL whose metadata
   names a different project than the one you asked for. Once the first release is
   out this becomes:

   .. code-block:: shell

     pip install schwaby

   Either way the import does not change:

   .. code-block:: python

     import schwab

   Those differ on purpose. Keeping ``schwab`` as the import makes this a drop-in
   replacement --- a consumer changes one line of ``requirements.txt`` and nothing else.

   .. warning::

     **The consequence is that** ``schwaby`` **and the original** ``schwab-py`` **cannot be
     installed together.** Both provide the ``schwab`` package, so whichever is installed
     second silently overwrites the other's files. ``pip`` does not warn, nothing fails at
     install time, and the first sign is behaviour from a version you did not choose. If you
     are migrating, uninstall ``schwab-py`` first.

   The plain install is three packages, because the interactive login flow lives in an
   extra. **Install** ``schwaby[login]`` **if you call** ``easy_client`` **or**
   ``client_from_login_flow`` --- including when you already have a token file, since
   ``easy_client`` re-authenticates through the login flow once the token passes
   ``max_token_age`` (6.5 days by default). Calling either without the extra raises an
   ``ImportError`` saying so. ``schwaby[codegen]`` covers the order-code generator.
   Notebook users need neither: there ``easy_client`` uses the manual flow.

   **Bug reports and questions go to** `the issue tracker
   <https://github.com/Hu1kSmash/schwaby/issues>`__.

.. image:: https://github.com/Hu1kSmash/schwaby/workflows/tests/badge.svg
  :target: https://github.com/Hu1kSmash/schwaby/actions?query=workflow%3Atests

What is ``schwaby``?
----------------------

``schwaby`` is an unofficial wrapper around the Charles Schwab Consumer APIs.  
It strives to be as thin and unopinionated as possible, offering an elegant 
programmatic interface over each endpoint. Notable functionality includes:

* Login and authentication
* Quotes, fundamentals, and historical pricing data
* Options chains
* Streaming quotes and order book depth data
* Order construction, placement and management
* Account info
* Synchronous and ``asyncio`` clients over the same interface

How do I use ``schwaby``?
---------------------------

For a full description of ``schwaby``'s functionality, check out the 
`documentation <https://github.com/Hu1kSmash/schwaby/blob/main/docs/index.rst>`__. Meanwhile,
here's a quick getting started guide:

Before you do anything, create an account and an application on the
`Charles Schwab developer site <https://developer.schwab.com/login>`__.
You'll receive an API key and app secret, which you can pass to this wrapper.  
You'll also want to take note of your callback URI, as the login flow requires 
it. You app must be approved by Schwab before you can use it (this can take 
several days).  You can find more detailed instructions `here 
<https://github.com/Hu1kSmash/schwaby/blob/main/docs/getting-started.rst>`__.

Next, install ``schwaby``. Note the distribution is ``schwaby`` while the
import stays ``schwab`` --- ``pip install schwab-py`` fetches the *original*
project, which is a different and much older codebase:

.. code-block:: shell

  pip install "schwaby[login]"

``[login]`` is there because the example below calls ``easy_client``, which
opens a browser login flow the first time it runs. Without it, the plain
``schwaby`` install is the three packages the library always needs. The interactive
login flow and the order-code generator each need an extra ---
``schwaby[login]`` and ``schwaby[codegen]`` --- because neither is used by a
program that loads its token from a file, and a bare install is twelve fewer
packages on a machine that places trades. Calling either without its extra says
so, and says what to install.

You're good to go! To demonstrate, here's how you can authenticate and fetch
daily historical price data for the past twenty years:

.. code-block:: python

  from schwab import auth, client
  import json

  api_key = 'YOUR_API_KEY'
  app_secret = 'YOUR_APP_SECRET'
  callback_url = 'https://127.0.0.1:8182/'
  token_path = '/path/to/token.json'

  c = auth.easy_client(api_key, app_secret, callback_url, token_path)

  r = c.get_price_history_every_day('AAPL')
  r.raise_for_status()
  print(json.dumps(r.json(), indent=4))

Why should I use ``schwaby``?
-------------------------------

Schwab's API is capable, but several corners of it are tedious to get right and
unforgiving when you get them wrong. ``schwaby`` takes on those corners and
stays out of your way everywhere else:

1. **Safe authentication.** Schwab's API supports OAuth authentication, but too
   many people online end up rolling their own implementation of the OAuth
   callback flow. This is both unnecessarily complex and dangerous.
   ``schwaby`` handles token fetch and refreshing for you.

2. **A usable streaming client.** Schwab's streamer is a raw websocket that
   identifies every field by number, and the same number means different things
   on different services --- field ``2`` is the ask price on
   ``LEVELONE_EQUITIES`` and the open price on ``CHART_EQUITY``. ``schwaby``
   carries the field tables for all thirteen services and relabels each message
   as it arrives, so you receive ``{'ASK_PRICE': 421.6, ...}`` rather than
   ``{'2': 421.6, ...}``. It also handles login and logout, keeps track of which
   response belongs to which request, and lets you register a handler per
   service rather than demultiplexing the stream yourself.

3. **Order construction Schwab will accept.** Order JSON is deeply nested, and a
   malformed order comes back rejected with little explanation of what was
   wrong. ``OrderBuilder`` assembles it from named parts and validates the
   values it can, and ``schwab.orders.equities`` and ``schwab.orders.options``
   provide ready-made templates for the common equity orders and option
   strategies. ``schwab.contrib.orders`` runs the process backwards: hand it an
   order you have already placed and it returns the builder that would place it
   again.

4. **Enums rather than magic strings.** Each endpoint's legal parameter values
   are enums on the client, so a misspelled projection or an invalid order
   duration fails immediately in Python instead of arriving as an opaque HTTP
   400 in the middle of a session.

5. **Minimal wrapping everywhere else.** Unlike some other API wrappers, which
   build in lots of logic and validation, ``schwaby`` takes raw values and
   returns the raw ``httpx2`` response, allowing you to interpret the complex API
   responses as you see fit. Anything you can do with raw HTTP requests you can
   do with ``schwaby``, only more easily.

The documentation linked above is worth reading even if you end up calling the
API directly. Schwab's own developer portal is behind a login, so for a good
deal of this API those pages are the most accessible description of how it
actually behaves.

Why should I *not* use ``schwaby``?
-------------------------------------

As excellent as Schwab's API is, there are a few popular features it does not 
offer: 

 * While Charles Schwab owns `thinkorswim (AKA TOS)
   <https://www.schwab.com/trading/thinkorswim/desktop>`__, this API is 
   unaffiliated with it. You can access and trade against the same accounts as 
   TOS, but some of TOS's functionality is not supported by ``schwaby``
 * Paper trading is not supported
 * Historical options pricing data is not available. 

What else?
----------

Bug reports, suggestions, and patches are welcome. Submit issues
`here <https://github.com/Hu1kSmash/schwaby/issues>`__ and pull requests `here <https://github.com/Hu1kSmash/schwaby/pulls>`__.

If the problem is with behaviour this project shares with
`alexgolec/schwab-py <https://github.com/alexgolec/schwab-py>`__ and is not one of the
changes listed in the changelog, it is worth reporting there too --- it will help more
people than a report here alone.

``schwaby`` is released under the
`MIT license <https://github.com/Hu1kSmash/schwaby/blob/main/LICENSE>`__, and remains
copyright Alex Golec.

**Disclaimer:** *schwaby is an unofficial API wrapper. It is in no way 
endorsed by or affiliated with Charles Schwab or any associated organization.
Make sure to read and understand the terms of service of the underlying API 
before using this package. This authors accept no responsibility for any
damage that might stem from use of this package. See the LICENSE file for
more details.*

