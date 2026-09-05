``schwaby``: An Unofficial Charles Schwab API Client
======================================================

.. image:: _static/github-logo.png
   :width: 40
   :target: https://github.com/Hu1kSmash/schwaby

``schwaby`` is an unofficial Python client for the Charles Schwab trading API. It
covers every endpoint Schwab publishes, turns the streaming websocket into
something you can read, builds orders Schwab will accept, and takes the sharp
edges off the parts that matter when the account is funded.

.. code-block:: shell

  pip install schwaby

The distribution is ``schwaby``; the importable package is ``schwab``. Note that
it cannot be installed alongside ``schwab-py``, which provides the same package
--- see :ref:`getting_started`.

New here? Start with :ref:`getting_started`, then :ref:`auth`.

.. toctree::
  :maxdepth: 2
  :caption: Contents:

  getting-started
  auth
  client
  streaming
  order-templates
  order-builder
  util
  help
  contributing



------------------------
Where this came from
------------------------

``schwaby`` began from `alexgolec/schwab-py
<https://github.com/alexgolec/schwab-py>`__, an MIT-licensed library by Alex
Golec which gave this project its shape and most of its code. It became a
separate project because running systematic strategies against funded accounts
imposes requirements a general-purpose wrapper has no particular reason to
prioritise --- prices that are never silently altered, a token file that
survives a crash, a stream that reports what it absorbs. Alex Golec's copyright
and licence are unchanged.

See the `changelog
<https://github.com/Hu1kSmash/schwaby/blob/main/CHANGELOG.md>`__ for what
changed, and the `README <https://github.com/Hu1kSmash/schwaby>`__ for the
longer version.

**Disclaimer:** *schwaby is an unofficial API wrapper. It is in no way 
endorsed by or affiliated with Charles Schwab or any associated organization.
Make sure to read and understand the terms of service of the underlying API 
before using this package. This authors accept no responsibility for any
damage that might stem from use of this package. See the LICENSE file for
more details.*
