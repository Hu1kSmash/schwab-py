``schwaby``: An Unofficial Charles Schwab API Client
======================================================

.. image:: _static/github-logo.png
   :width: 40
   :target: https://github.com/Hu1kSmash/schwaby

``schwaby`` is an unofficial Python client for the Charles Schwab API, built for
running automated strategies against real accounts.

.. note::

   ``schwaby`` began from `alexgolec/schwab-py
   <https://github.com/alexgolec/schwab-py>`__, an MIT-licensed library by Alex
   Golec which gave this project its shape and most of its code. It became a
   separate project because running systematic strategies against funded
   accounts imposes requirements a general-purpose wrapper has no particular
   reason to prioritise --- prices that are never silently altered, a token file
   that survives a crash, a stream that reports what it absorbs. See the
   `changelog <https://github.com/Hu1kSmash/schwaby/blob/main/CHANGELOG.md>`__
   for what changed, and the `README
   <https://github.com/Hu1kSmash/schwaby>`__ for the longer version.

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



**Disclaimer:** *schwaby is an unofficial API wrapper. It is in no way 
endorsed by or affiliated with Charles Schwab or any associated organization.
Make sure to read and understand the terms of service of the underlying API 
before using this package. This authors accept no responsibility for any
damage that might stem from use of this package. See the LICENSE file for
more details.*
