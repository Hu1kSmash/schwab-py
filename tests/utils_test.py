from unittest.mock import MagicMock
from schwab.utils import AccountHashMismatchException, Utils
from schwab.utils import (
    AccountHashMismatchException,
    MissingLocationHeaderError,
    OrderIdNotFoundError,
    SchwabError,
    UnrecognizedLocationError,
    UnsuccessfulOrderException,
)
from schwab.utils import EnumEnforcer
from .utils import no_duplicates, MockResponse

import enum
import unittest


class EnumEnforcerTest(unittest.TestCase):

    class TestClass(EnumEnforcer):
        def test_enforcement(self, value):
            self.convert_enum(value, EnumEnforcerTest.TestEnum)


    class TestEnum(enum.Enum):
        VALUE_1 = 1
        VALUE_2 = 2


    def test_valid_enum(self):
        t = self.TestClass(enforce_enums=True)
        t.test_enforcement(self.TestEnum.VALUE_1)

    def test_invalid_enum_passed_as_string(self):
        t = self.TestClass(enforce_enums=True)
        with self.assertRaisesRegex(
                ValueError, 'tests.utils_test.TestEnum.VALUE_1'):
            t.test_enforcement('VALUE_1')

    def test_invalid_enum_passed_as_not_string(self):
        t = self.TestClass(enforce_enums=True)
        with self.assertRaises(ValueError):
            t.test_enforcement(123)


class UtilsTest(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        self.account_hash = '0xacc0unth45h'
        self.utils = Utils(self.mock_client, self.account_hash)

        self.order_id = 1

        self.maxDiff = None

    ##########################################################################
    # extract_order_id tests

    @no_duplicates
    def test_extract_order_id_order_not_ok(self):
        # assertRaises' `msg` is the message printed when the *assertion*
        # fails, not a pattern the exception has to match -- so the version of
        # this test that passed `msg='order not successful'` asserted nothing
        # about the exception at all and would have passed on any wording.
        response = MockResponse({}, 403)
        with self.assertRaisesRegex(
                UnsuccessfulOrderException, 'order not successful: status 403'):
            self.utils.extract_order_id(response)

    @no_duplicates
    def test_a_rejection_carries_schwabs_own_explanation(self):
        # A status code does not distinguish a malformed order from one the
        # account cannot afford. Schwab types an error body as
        # {"message": ..., "errors": [...]}, and that is the only place the
        # reason appears.
        response = MockResponse(
                {'message': 'Order validation failed',
                 'errors': ['Insufficient buying power']}, 400)

        with self.assertRaises(UnsuccessfulOrderException) as cm:
            self.utils.extract_order_id(response)

        self.assertIn('Order validation failed', str(cm.exception))
        self.assertIn('Insufficient buying power', str(cm.exception))
        self.assertIs(response, cm.exception.response)

    @no_duplicates
    def test_a_rejection_with_no_readable_body_still_raises(self):
        # The formatter runs on the failure path, so anything it cannot read
        # has to yield no detail rather than an exception of its own --
        # replacing a useful error with a useless one is worse than terse.
        class Unreadable(MockResponse):
            def json(self):
                raise ValueError('not json')

        response = Unreadable({}, 500)
        with self.assertRaisesRegex(
                UnsuccessfulOrderException, 'order not successful: status 500'):
            self.utils.extract_order_id(response)

    @no_duplicates
    def test_a_long_explanation_is_bounded(self):
        # This lands in a log line. The whole body stays reachable on
        # .response for anyone who wants the rest of it.
        response = MockResponse({'message': 'x' * 5000}, 400)

        with self.assertRaises(UnsuccessfulOrderException) as cm:
            self.utils.extract_order_id(response)

        self.assertLess(len(str(cm.exception)), 700)
        self.assertIn('truncated', str(cm.exception))
        self.assertEqual(5000, len(cm.exception.response.json()['message']))

    @no_duplicates
    def test_no_location_header_raises_rather_than_returning_none(self):
        # Both of these used to return None, which is also what plenty of
        # harmless things return, so `if order_id:` skipped an order Schwab had
        # very likely placed.
        response = MockResponse({}, 200, headers={})

        with self.assertRaises(MissingLocationHeaderError) as cm:
            self.utils.extract_order_id(response)

        self.assertIsNone(cm.exception.location)
        self.assertIs(response, cm.exception.response)
        self.assertIn('may be live', str(cm.exception))

    @no_duplicates
    def test_unparsable_location_raises_and_carries_the_header(self):
        response = MockResponse({}, 200, headers={'Location': 'not-a-match'})

        with self.assertRaises(UnrecognizedLocationError) as cm:
            self.utils.extract_order_id(response)

        # The header is the whole of the evidence for a bug report.
        self.assertEqual('not-a-match', cm.exception.location)
        self.assertIn('not-a-match', str(cm.exception))

    @no_duplicates
    def test_both_are_catchable_as_one_thing(self):
        # A caller that just wants "I have no order id" should not have to name
        # both, and should not accidentally catch a rejection with them.
        for headers in ({}, {'Location': 'not-a-match'}):
            with self.assertRaises(OrderIdNotFoundError):
                self.utils.extract_order_id(MockResponse({}, 200, headers=headers))

        self.assertFalse(
                issubclass(UnsuccessfulOrderException, OrderIdNotFoundError))

    @no_duplicates
    def test_a_broad_except_valueerror_does_not_swallow_it(self):
        # The point of raising was that a live, untracked order must not be
        # silent. Inheriting ValueError would have handed that back: it is the
        # idiom people reach for around int() and float(), and order specs
        # coerce exactly those a few lines from this call.
        self.assertFalse(issubclass(OrderIdNotFoundError, ValueError))

        with self.assertRaises(OrderIdNotFoundError):
            try:
                self.utils.extract_order_id(MockResponse({}, 200, headers={}))
            except ValueError:                       # pragma: no cover
                self.fail('a broad except ValueError swallowed it')

    @no_duplicates
    def test_the_two_siblings_keep_valueerror(self):
        # They had it before SchwabError existed, and code catching them that
        # way predates this release. Dropping it would break that for no gain;
        # they describe a caller mistake, which is what ValueError means.
        self.assertTrue(issubclass(UnsuccessfulOrderException, ValueError))
        self.assertTrue(issubclass(AccountHashMismatchException, ValueError))

    @no_duplicates
    def test_schwab_error_covers_every_exception_the_library_defines(self):
        # A base that covers most of them is worse than none: it invites
        # `except SchwabError` as a complete guard and is quietly not one.
        import importlib, inspect
        found, missing = 0, []
        for name in ('schwab.auth', 'schwab.utils', 'schwab.streaming',
                     'schwab.orders.common', 'schwab.orders.generic',
                     'schwab.client.base', 'schwab.contrib.util'):
            module = importlib.import_module(name)
            for attr, obj in vars(module).items():
                if (inspect.isclass(obj) and issubclass(obj, BaseException)
                        and obj.__module__ == name):
                    found += 1
                    if not issubclass(obj, SchwabError):
                        missing.append('%s.%s' % (name, attr))

        self.assertGreater(found, 10)     # the walk actually found them
        self.assertEqual([], missing)

    @no_duplicates
    def test_the_two_causes_are_distinguishable(self):
        # Without this, aliasing the two classes together passes every other
        # test here: each raise site names its own class, so both
        # assertRaises calls still match. Found by mutation, not by reading.
        self.assertIsNot(MissingLocationHeaderError, UnrecognizedLocationError)

        missing = MockResponse({}, 200, headers={})
        unparsable = MockResponse({}, 200, headers={'Location': 'nope'})

        # Catching one must not catch the other. A caller reconciling a
        # possibly-live order may want to treat a changed URL format -- which
        # is our bug -- differently from a header Schwab never sent.
        with self.assertRaises(MissingLocationHeaderError):
            self.utils.extract_order_id(missing)
        with self.assertRaises(UnrecognizedLocationError):
            try:
                self.utils.extract_order_id(unparsable)
            except MissingLocationHeaderError:      # pragma: no cover
                self.fail('unparsable Location raised the missing-header type')

    @no_duplicates
    def test_get_order_nonmatching_account_hash(self):
        response = MockResponse({}, 200, headers={
            'Location':
            'https://api.schwabapi.com/trader/v1/accounts/badhash/orders/123'})
        with self.assertRaisesRegex(
                AccountHashMismatchException,
                'order request account hash != Utils.account_hash') as cm:
            self.utils.extract_order_id(response)

    @no_duplicates
    def test_get_order_success_200(self):
        order_id = 123456
        response = MockResponse({}, 200, headers={
            'Location':
            'https://api.schwabapi.com/trader/v1/accounts/{}/orders/{}'.format(
                self.account_hash, order_id)})
        self.assertEqual(order_id, self.utils.extract_order_id(response))

    @no_duplicates
    def test_get_order_success_201(self):
        order_id = 123456
        response = MockResponse({}, 201, headers={
            'Location':
            'https://api.schwabapi.com/trader/v1/accounts/{}/orders/{}'.format(
                self.account_hash, order_id)})
        self.assertEqual(order_id, self.utils.extract_order_id(response))
