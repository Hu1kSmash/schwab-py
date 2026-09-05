.. _utils:

=========
Utilities
=========

This section describes miscellaneous utility methods provided by ``schwaby``.  
All utilities are presented under the ``Utils`` class:

.. autoclass:: schwab.utils.Utils

  .. automethod:: __init__
  .. automethod:: set_account_hash


.. _extract_order_id:

---------------------------------------
Extract an order ID from a placed order
---------------------------------------

For successfully placed orders, :meth:`place_order 
<schwab.client.Client.place_order>` returns the ID of the newly created order, 
encoded in the ``r.headers['Location']`` header.  This method inspects the 
response and extracts the order ID from the contents, if it's there. This order 
ID can then be used to monitor or modify the order as described in the 
:ref:`Client documentation <orders-section>`. Example usage:

.. code-block:: python

  # Assume client and order already exist and are valid
  account_hash = client.get_account_numbers().json()[0]['hashValue']
  r = client.place_order(account_hash, order)
  order_id = Utils(client, account_hash).extract_order_id(r)

Every outcome other than success raises, so there is no ``None`` to check for.
The one worth handling deliberately is
:class:`~schwab.utils.OrderIdNotFoundError`: Schwab accepted the order and did
not give back an ID, which means **the order may be live** and you have no
handle on it.

.. code-block:: python

  from schwab.utils import OrderIdNotFoundError, UnsuccessfulOrderException

  try:
      order_id = Utils(client, account_hash).extract_order_id(r)
  except UnsuccessfulOrderException as exc:
      # Nothing was placed. Schwab's own reason is in the message.
      log.error('rejected: %s', exc)
  except OrderIdNotFoundError as exc:
      # Something probably was placed. Go and find it.
      log.error('placed but untracked: %s', exc)
      reconcile_recent_orders(account_hash)

.. automethod:: schwab.utils.Utils.extract_order_id


.. _exceptions:

++++++++++
Exceptions
++++++++++

The exceptions this library raises that a caller might reasonably catch.
:class:`~schwab.streaming.UnexpectedResponse`,
:class:`~schwab.streaming.UnexpectedResponseCode`,
:class:`~schwab.streaming.UnparsableMessage` and
:class:`~schwab.streaming.UnusableMessage` are streaming-specific and are
covered in :ref:`the streaming documentation <error_handlers>`.

.. autoclass:: schwab.utils.UnsuccessfulOrderException
  :members:

.. autoclass:: schwab.utils.OrderIdNotFoundError
  :members:

.. autoclass:: schwab.utils.MissingLocationHeaderError

.. autoclass:: schwab.utils.UnrecognizedLocationError

.. autoclass:: schwab.utils.AccountHashMismatchException

.. autoclass:: schwab.orders.common.InvalidOrderException


``TokenRefreshError`` is documented under :ref:`auth` with the retry guidance it
needs, and is not repeated here.

.. autoclass:: schwab.auth.RedirectTimeoutError

.. autoclass:: schwab.auth.RedirectServerExitedError
