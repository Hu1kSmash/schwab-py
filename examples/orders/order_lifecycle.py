"""Placing an order and finding out what happened to it.

Four steps, and the interesting parts are the failures rather than the happy
path:

  1. place the order
  2. get its id back out of the response
  3. poll until it reaches a terminal state
  4. cancel it if it never does

The documentation covers each call. What it cannot show is that step 2 has
three distinct outcomes -- the venue rejected it, the response was fine but
carried no order id, or you got an id -- and that they want different
handling.
"""

import time

import httpx2

import schwab
from schwab.orders.equities import equity_buy_limit
from schwab.utils import (
    AccountHashMismatchException,
    UnsuccessfulOrderException,
    Utils,
)

API_KEY = 'XXXXXX'
APP_SECRET = 'XXXXXX'
TOKEN_PATH = './token.json'

# Deliberately far from the market so this does not fill while you read it.
SYMBOL = 'AAPL'
QUANTITY = 1
LIMIT_PRICE = '1.00'      # a string, never a float -- see the README

# Anything not in this set is still live and worth waiting on.
TERMINAL = {'FILLED', 'CANCELED', 'REJECTED', 'EXPIRED', 'REPLACED'}

POLL_EVERY = 2.0
GIVE_UP_AFTER = 60.0


def place(client, account_hash):
    """Returns the order id, or None if the order did not produce one."""
    order = equity_buy_limit(SYMBOL, QUANTITY, LIMIT_PRICE).build()

    response = client.place_order(account_hash, order)

    try:
        return Utils(client, account_hash).extract_order_id(response)
    except UnsuccessfulOrderException as exc:
        # Schwab's own words for the rejection are in the message, and the
        # whole response is on the exception. A status code alone does not
        # separate a malformed order from one the account cannot afford.
        print('rejected: %s' % exc)
        print('body: %s' % exc.response.text)
        return None
    except AccountHashMismatchException:
        # The response is for a different account than this Utils was built
        # with. Worth its own branch: it means the wiring is wrong, not the
        # order.
        raise


def wait_for(client, account_hash, order_id):
    """Polls until the order reaches a terminal state, or the deadline passes."""
    deadline = time.time() + GIVE_UP_AFTER

    while time.time() < deadline:
        response = client.get_order(order_id, account_hash)
        response.raise_for_status()
        status = response.json()['status']

        print('status: %s' % status)
        if status in TERMINAL:
            return status

        time.sleep(POLL_EVERY)

    return None


def main():
    client = schwab.auth.client_from_token_file(
            TOKEN_PATH, api_key=API_KEY, app_secret=APP_SECRET)

    accounts = client.get_account_numbers()
    accounts.raise_for_status()
    account_hash = accounts.json()[0]['hashValue']

    order_id = place(client, account_hash)

    if order_id is None:
        # Either the order was rejected -- already reported above -- or it was
        # accepted and the response carried no Location header to read an id
        # from. `extract_order_id` returns None for both, so if you need to
        # tell them apart, check the response yourself before calling it.
        print('no order id; nothing to follow')
        return

    print('placed order %s' % order_id)

    status = wait_for(client, account_hash, order_id)

    if status is None:
        print('still live after %.0fs; cancelling' % GIVE_UP_AFTER)
        cancelled = client.cancel_order(order_id, account_hash)
        # Cancelling an order that filled a moment ago is not an error in your
        # code, it is a race you lost. Check rather than assume.
        if cancelled.status_code == httpx2.codes.OK:
            print('cancelled')
        else:
            print('cancel refused: %s' % cancelled.text)


if __name__ == '__main__':
    main()
