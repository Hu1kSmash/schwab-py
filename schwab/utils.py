'''Implements additional functionality beyond what's implemented in the client
module.'''

import re


def class_fullname(o):
    return o.__module__ + '.' + o.__name__


class EnumEnforcer:
    def __init__(self, enforce_enums):
        self.enforce_enums = enforce_enums

    def type_error(self, value, required_enum_type):
        possible_members_message = ''

        if isinstance(value, str):
            possible_members = []
            for member in required_enum_type.__members__:
                fullname = class_fullname(required_enum_type) + '.' + member
                if value in fullname:
                    possible_members.append(fullname)

            # Oxford comma insertion
            if possible_members:
                possible_members_message = 'Did you mean ' + ', '.join(
                    possible_members[:-2] + [' or '.join(
                        possible_members[-2:])]) + '? '

        raise ValueError(
            ('expected type "{}", got type "{}". {}(initialize with ' +
             'enforce_enums=False to disable this checking)').format(
                required_enum_type.__name__,
                type(value).__name__,
                possible_members_message))

    def convert_enum(self, value, required_enum_type):
        if value is None:
            return None

        if isinstance(value, required_enum_type):
            return value.value
        elif self.enforce_enums:
            self.type_error(value, required_enum_type)
        else:
            return value

    def convert_enum_iterable(self, iterable, required_enum_type):
        if iterable is None:
            return None

        if isinstance(iterable, required_enum_type):
            return [iterable.value]

        values = []
        for value in iterable:
            if isinstance(value, required_enum_type):
                values.append(value.value)
            elif self.enforce_enums:
                self.type_error(value, required_enum_type)
            else:
                values.append(value)
        return values

    def set_enforce_enums(self, enforce_enums):
        self.enforce_enums = enforce_enums


def _describe_error(response):
    '''Schwab's own words for a rejection, as a suffix, or the empty string.

    Bounded, because this ends up in an exception message and from there in
    somebody's logs: an unbounded body would put an entire order echo on one
    line. The whole response stays reachable as the exception's ``.response``
    for anyone who needs the rest.

    Anything unexpected yields no suffix rather than an error of its own. This
    runs on the failure path, and a formatter that raises there would replace a
    useful exception with a useless one.
    '''
    try:
        body = response.json()
        if not isinstance(body, dict):
            return ''
        parts = []
        message = body.get('message')
        if isinstance(message, str) and message.strip():
            parts.append(message.strip())
        errors = body.get('errors')
        if isinstance(errors, (list, tuple)):
            parts.extend(e.strip() for e in errors
                         if isinstance(e, str) and e.strip())
        if not parts:
            return ''
        detail = '; '.join(parts)
        if len(detail) > _ERROR_DETAIL_LIMIT:
            detail = detail[:_ERROR_DETAIL_LIMIT] + '... (truncated, see .response)'
        return ': ' + detail
    except Exception:
        return ''


_ERROR_DETAIL_LIMIT = 500


class UnsuccessfulOrderException(ValueError):
    '''
    Raised by :meth:`Utils.extract_order_id` when attempting to extract an
    order ID from a :meth:`Client.place_order` response that was not successful.

    The rejected response is on the exception as ``.response``, and Schwab's own
    explanation is in the message when there was one. Schwab types an error body
    as ``{"message": ..., "errors": [...]}``, and that text is the only place
    the reason for a rejection appears -- a status code alone does not
    distinguish a malformed order from one the account cannot afford.
    '''

    def __init__(self, response, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response = response


class OrderIdNotFoundError(ValueError):
    '''
    Raised by :meth:`Utils.extract_order_id` when Schwab accepted the order but
    the response did not yield an order ID.

    **The order may be live.** Schwab returned a success status, so the order
    was very likely placed; what is missing is the handle you would use to
    watch or cancel it. Treat this as "go and look", not as "nothing
    happened" --- :meth:`Client.get_orders_for_account` over a recent time
    window will find it.

    Until 3.0.0 both of the conditions below returned ``None``, which is the
    same value a caller gets from plenty of harmless things, so the usual
    handling was ``if order_id:`` and a live order went untracked.

    ``.response`` is the ``place_order`` response. ``.location`` is the raw
    ``Location`` header, or ``None`` when there was not one.

    .. warning::

       This subclasses ``ValueError``, for consistency with the other
       exceptions here. So a broad ``except ValueError`` anywhere on your
       placement path will swallow it, and the thing it is warning you about
       --- a live order with no handle --- goes back to being silent. If you
       have one of those, narrow it.
    '''

    def __init__(self, response, location, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response = response
        self.location = location


class MissingLocationHeaderError(OrderIdNotFoundError):
    '''The response carried no ``Location`` header at all.

    Catch :class:`OrderIdNotFoundError` unless you specifically need to tell
    this apart from :class:`UnrecognizedLocationError`.
    '''


class UnrecognizedLocationError(OrderIdNotFoundError):
    '''The ``Location`` header was present and did not look like an order URL.

    Most likely Schwab changed the format. The header is on the exception as
    ``.location`` --- please include it in a bug report.
    '''


class AccountHashMismatchException(ValueError):
    '''
    Raised by :meth:`Utils.extract_order_id` when attempting to extract an
    order ID from a :meth:`Client.place_order` with a different account hash
    than the one with which the :class:`Utils` was initialized.
    '''


class TokenRefreshError(Exception):
    '''
    Raised when Schwab rejects an attempt to refresh the OAuth token.

    Every request refreshes the token first if it is close to expiring, so this
    surfaces from an ordinary call rather than from anything token-shaped. It
    exists so that an unattended application can catch a failure to refresh
    without importing ``authlib`` and catching an exception type this library
    never mentions. The original error is preserved as ``__cause__``.

    ``token_age`` is the number of seconds since the token was originally
    authorized, or ``None`` if this client was built without token metadata.
    Schwab documents a refresh token as valid for seven days after creation,
    and refreshing does not extend that, so a ``token_age`` past 604800 means
    the window has closed and no amount of retrying will help -- someone has to
    complete the login flow again.

    ``refresh_token_invalid`` is ``True`` when no amount of retrying will
    produce a working token, and only the full authorization_code flow -- which
    needs a human at a browser -- will help. That covers two cases: Schwab
    saying the refresh token is invalid, expired or revoked, and the stored
    token being unusable before anything is even sent, which the underlying
    OAuth library reports without contacting Schwab at all.

    It is ``False`` for everything else, *including* failures this library did
    not recognize -- the conservative direction, since treating a recoverable
    failure as terminal would stop an application which only needed to try
    again.
    '''

    def __init__(self, message, *, token_age=None, refresh_token_invalid=False):
        super().__init__(message)

        #: Seconds since the token was originally authorized, or ``None``.
        self.token_age = token_age

        #: ``True`` when the refresh token is invalid, expired or revoked, and
        #: only a new login flow will help. ``False`` when the failure may be
        #: transient, or was not recognized.
        self.refresh_token_invalid = refresh_token_invalid


class LazyLog:
    'Helper to defer evaluation of expensive variables in log messages'
    def __init__(self, func):
        self.func = func
    def __str__(self):
        return self.func()


class Utils(EnumEnforcer):
    '''Helper for placing orders on equities. Provides easy-to-use
    implementations for common tasks such as market and limit orders.'''

    def __init__(self, client, account_hash):
        '''Creates a new ``Utils`` instance. For convenience, this object
        assumes the user wants to work with a single account hash at a time.'''
        super().__init__(True)

        self.client = client
        self.account_hash = account_hash

    def set_account_hash(self, account_hash):
        '''Set the account hash used by this ``Utils`` instance.'''
        self.account_hash = account_hash

    def extract_order_id(self, place_order_response):
        '''Extracts the order ID from a response returned by
        :meth:`Client.place_order() <schwab.client.Client.place_order>`.

        Every outcome other than success raises, and each one raises something
        different, because they call for different handling:

        * :class:`UnsuccessfulOrderException` --- Schwab rejected the order.
          Its own explanation is in the message and the whole response is on
          the exception. Nothing was placed.
        * :class:`MissingLocationHeaderError` and
          :class:`UnrecognizedLocationError` --- Schwab accepted the order and
          the ID could not be read. **The order may be live.** Both subclass
          :class:`OrderIdNotFoundError`, so catch that unless you need to tell
          them apart.
        * :class:`AccountHashMismatchException` --- the response belongs to a
          different account than this :class:`Utils` was built with, which
          means the wiring is wrong rather than the order.

        Until 3.0.0 the two middle cases returned ``None`` instead, and shared
        that value with each other. A caller writing ``if order_id:`` therefore
        skipped tracking an order that had very likely been placed.

        :param place_order_response: Response from
                                     :meth:`Client.place_order()
                                     <schwab.client.Client.place_order>`.
        '''
        if place_order_response.is_error:
            raise UnsuccessfulOrderException(
                    place_order_response,
                    'order not successful: status {}{}'.format(
                        place_order_response.status_code,
                        _describe_error(place_order_response)))

        try:
            location = place_order_response.headers['Location']
        except KeyError:
            raise MissingLocationHeaderError(
                    place_order_response, None,
                    'order was accepted but the response carried no Location '
                    'header, so it has no order ID to return. The order may be '
                    'live: check get_orders_for_account.')

        m = re.match(
                r'https://api.schwabapi.com/trader/v1/accounts/(\w+)/orders/(\d+)',
                location)

        if m is None:
            raise UnrecognizedLocationError(
                    place_order_response, location,
                    'order was accepted but its Location header does not look '
                    'like an order URL, so it has no order ID to return. The '
                    'order may be live: check get_orders_for_account. Header '
                    'was: {!r}'.format(location))
        account_hash, order_id = m.group(1), int(m.group(2))

        if str(account_hash) != str(self.account_hash):
            raise AccountHashMismatchException(
                'order request account hash != Utils.account_hash')

        return order_id
