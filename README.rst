``schwab-py``: A Charles Schwab API Wrapper
===========================================

.. note::

   **This is a maintained fork of**
   `alexgolec/schwab-py <https://github.com/alexgolec/schwab-py>`__.

   The original is the work of Alex Golec and remains the upstream project. This fork exists
   because upstream has not merged a change since August 2025, while several defects affecting
   correctness under live trading remained open — prices silently a cent low when passed as
   floats, a token file that a crash during a refresh could destroy, a stream that could wedge
   permanently on an unanswered request, and a deprecated ``websockets`` import that will stop
   importing when it is removed. See `CHANGELOG.md
   <https://github.com/Hu1kSmash/schwab-py/blob/main/CHANGELOG.md>`__ for the full list.

   **Every change here has also been offered upstream as a pull request.** This is not a
   competing project and it is not a criticism of the original author, who wrote essentially all
   of the code below. If upstream merges those changes, the fork's divergence shrinks; if
   upstream resumes active maintenance, using it again is the better choice.

   The importable package is still ``schwab``, so this is a drop-in replacement. It is not
   published to PyPI — install it from git, pinned to a tag or commit:

   .. code-block:: shell

     pip install "schwab-py @ git+https://github.com/Hu1kSmash/schwab-py@v1.6.0"

   Note that installing this alongside the PyPI ``schwab-py`` will conflict, since both provide
   the ``schwab`` package. Pick one.

   Issues and pull requests specific to this fork belong on `its own tracker
   <https://github.com/Hu1kSmash/schwab-py/issues>`__. Anything not caused by the changes listed
   in the changelog is better reported upstream, where it will help more people.

.. image:: https://github.com/Hu1kSmash/schwab-py/workflows/tests/badge.svg
  :target: https://github.com/Hu1kSmash/schwab-py/actions?query=workflow%3Atests

What is ``schwab-py``?
----------------------

``schwab-py`` is an unofficial wrapper around the Charles Schwab Consumer APIs.  
It strives to be as thin and unopinionated as possible, offering an elegant 
programmatic interface over each endpoint. Notable functionality includes:

* Login and authentication
* Quotes, fundamentals, and historical pricing data
* Options chains
* Streaming quotes and order book depth data
* Trades and trade management
* Account info

How do I use ``schwab-py``?
---------------------------

For a full description of ``schwab-py``'s functionality, check out the 
`documentation <https://github.com/Hu1kSmash/schwab-py/blob/main/docs/index.rst>`__. Meanwhile,
here's a quick getting started guide:

Before you do anything, create an account and an application on the
`Charles Schwab developer site <https://developer.schwab.com/login>`__.
You'll receive an API key and app secret, which you can pass to this wrapper.  
You'll also want to take note of your callback URI, as the login flow requires 
it. You app must be approved by Schwab before you can use it (this can take 
several days).  You can find more detailed instructions `here 
<https://github.com/Hu1kSmash/schwab-py/blob/main/docs/getting-started.rst>`__.

Next, install ``schwab-py``:

.. code-block:: python

  pip install schwab-py

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

Why should I use ``schwab-py``?
-------------------------------

``schwab-py`` was designed to provide a few important pieces of functionality:

1. **Safe Authentication**: Schwab's API supports OAuth authentication, but too 
   many people online end up rolling their own implementation of the OAuth 
   callback flow. This is both unnecessarily complex and dangerous.  
   ``schwab-py`` handles token fetch and refreshing for you.

2. **Minimal API Wrapping**: Unlike some other API wrappers, which build in lots 
   of logic and validation, ``schwab-py`` takes raw values and returns raw 
   responses, allowing you to interpret the complex API responses as you see 
   fit. Anything you can do with raw HTTP requests you can do with 
   ``schwab-py``, only more easily.

Why should I *not* use ``schwab-py``?
-------------------------------------

As excellent as Schwab's API is, there are a few popular features it does not 
offer: 

 * While Charles Schwab owns `thinkorswim (AKA TOS)
   <https://www.schwab.com/trading/thinkorswim/desktop>`__, this API is 
   unaffiliated with it. You can access and trade against the same accounts as 
   TOS, but some of TOS's functionality is not supported by ``schwab-py``
 * Paper trading is not supported
 * Historical options pricing data is not available. 

What else?
----------

Bug reports, suggestions, and patches are welcome. Submit issues
`here <https://github.com/Hu1kSmash/schwab-py/issues>`__ and pull requests `here <https://github.com/Hu1kSmash/schwab-py/pulls>`__.

Please read the fork notice at the top first: problems which are not caused by
this fork's changes are usually better reported `upstream
<https://github.com/alexgolec/schwab-py/issues>`__.

``schwab-py`` is released under the
`MIT license <https://github.com/Hu1kSmash/schwab-py/blob/main/LICENSE>`__, and remains
copyright Alex Golec.

**Disclaimer:** *schwab-py is an unofficial API wrapper. It is in no way 
endorsed by or affiliated with Charles Schwab or any associated organization.
Make sure to read and understand the terms of service of the underlying API 
before using this package. This authors accept no responsibility for any
damage that might stem from use of this package. See the LICENSE file for
more details.*

