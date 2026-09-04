import datetime
import unittest

from schwab.orders.common import *
from schwab.orders.options import *
from ..utils import has_diff, no_duplicates


class OptionSymbolTest(unittest.TestCase):

    @no_duplicates
    def test_parse_success_put(self):
        op = OptionSymbol.parse_symbol('AAPL  261218P00350000')
        self.assertEqual(op.underlying_symbol, 'AAPL')
        self.assertEqual(
                op.expiration_date, datetime.date(
                    year=2026, month=12, day=18))
        self.assertEqual(op.contract_type, 'P')
        self.assertEqual(op.strike_price, '350')

        self.assertEqual('AAPL  261218P00350000', op.build())

    def test_parse_success_call(self):
        op = OptionSymbol.parse_symbol('AAPL  240510C00100000')
        self.assertEqual(op.underlying_symbol, 'AAPL')
        self.assertEqual(
                op.expiration_date, datetime.date(
                    year=2024, month=5, day=10))
        self.assertEqual(op.contract_type, 'C')
        self.assertEqual(op.strike_price, '100')

        self.assertEqual('AAPL  240510C00100000', op.build())

    def test_short_symbol(self):
        op = OptionSymbol.parse_symbol('V     240510C00145000')
        self.assertEqual(op.underlying_symbol, 'V')
        self.assertEqual(
                op.expiration_date, datetime.date(
                    year=2024, month=5, day=10))
        self.assertEqual(op.contract_type, 'C')
        self.assertEqual(op.strike_price, '145')

        self.assertEqual('V     240510C00145000', op.build())

    def test_decimal_in_price(self):
        op = OptionSymbol.parse_symbol('V     240510C00145000')
        self.assertEqual(op.underlying_symbol, 'V')
        self.assertEqual(
                op.expiration_date, datetime.date(
                    year=2024, month=5, day=10))
        self.assertEqual(op.contract_type, 'C')
        self.assertEqual(op.strike_price, '145')

        self.assertEqual('V     240510C00145000', op.build())

    def test_strike_over_1000(self):
        op = OptionSymbol.parse_symbol('BKNG  240510C02400000')
        self.assertEqual(op.underlying_symbol, 'BKNG')
        self.assertEqual(
                op.expiration_date, datetime.date(
                    year=2024, month=5, day=10))
        self.assertEqual(op.contract_type, 'C')
        self.assertEqual(op.strike_price, '2400')

        self.assertEqual('BKNG  240510C02400000', op.build())

    def test_strike_is_encoded_in_decimal_not_binary(self):
        # The strike is scaled by 1000 to build the symbol. Doing that on a
        # binary float and truncating with int() truncates the representation
        # error with it: 2.01 * 1000 is 2009.9999999999998, so int() gives
        # 2009 and the symbol names a strike a tenth of a cent low -- a
        # different contract, or one that does not exist. This is the same
        # defect that made limit prices a cent low, in a different function.
        for strike, expected in (('2.01', '00002010'), ('4.02', '00004020'),
                                 ('8.19', '00008190'), ('2.03', '00002030')):
            op = OptionSymbol('AAPL', datetime.date(2024, 5, 10), 'C', strike)
            self.assertTrue(
                    op.build().endswith(expected),
                    '{} encoded as {}, expected to end {}'.format(
                        strike, op.build(), expected))

    def test_every_cent_granular_strike_encodes_exactly(self):
        # The sweep the single cases above are drawn from: every cent from
        # $0.01 to $1000.00. 590 of these were wrong before the fix.
        import decimal
        wrong = []
        for cents in range(1, 100001):
            strike = '{:.2f}'.format(cents / 100)
            built = OptionSymbol(
                    'AAPL', datetime.date(2024, 5, 10), 'C', strike).build()
            if int(built[-8:]) != int(decimal.Decimal(strike) * 1000):
                wrong.append(strike)
                if len(wrong) > 5:
                    break
        self.assertEqual([], wrong)

    def test_strike_ends_in_decimal_point(self):
        op = OptionSymbol('AAPL', datetime.date(2024, 5, 10), 'C', '100.')
        self.assertEqual('AAPL  240510C00100000', op.build())

    def test_strike_ends_in_trailing_zeroes(self):
        op = OptionSymbol('AAPL', datetime.date(2024, 5, 10), 'C', 
                          '100.00000000')
        self.assertEqual('AAPL  240510C00100000', op.build())

    def test_CALL_as_delimiter(self):
        op = OptionSymbol('AAPL', datetime.date(2024, 5, 10), 'CALL', '100.10')
        self.assertEqual('AAPL  240510C00100100', op.build())

    def test_PUT_as_delimiter(self):
        op = OptionSymbol('AAPL', datetime.date(2024, 5, 10), 'CALL', '100.10')
        self.assertEqual('AAPL  240510C00100100', op.build())

    def test_invalid_strike(self):
        with self.assertRaisesRegex(
                ValueError, '.*option must have contract type.*'):
            op = OptionSymbol.parse_symbol('BKNG  240510Q02400000')


    def test_date_as_string(self):
        op = OptionSymbol('AAPL', '261218', 'P', '350')
        self.assertEqual('AAPL  261218P00350000', op.build())


    def test_strike_as_float(self):
        with self.assertRaisesRegex(
                ValueError, '.*strike price must be a string.*'):
            op = OptionSymbol('AAPL', datetime.date(2024, 5, 10), 'C', 183.05)


    def test_strike_as_invalid_string(self):
        with self.assertRaisesRegex(
                ValueError, '.*strike price must be a string.*'):
            op = OptionSymbol(
                    'AAPL', datetime.date(2024, 5, 10), 'C', 'bogus-strike')


    def test_strike_negative(self):
        with self.assertRaisesRegex(
                ValueError, '.*strike price must be a string.*'):
            op = OptionSymbol(
                    'AAPL', datetime.date(2024, 5, 10), 'C', '-150.0')


    def test_strike_zero(self):
        with self.assertRaisesRegex(
                ValueError, '.*strike price must be a string.*'):
            op = OptionSymbol(
                    'AAPL', datetime.date(2024, 5, 10), 'C', '0')


class OptionTemplatesTest(unittest.TestCase):

    # Buy to open

    @no_duplicates
    def test_option_buy_to_open_market(self):
        self.assertFalse(has_diff({
            'orderType': 'MARKET',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'BUY_TO_OPEN',
                'quantity': 10,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }]
        }, option_buy_to_open_market('GOOG_012122P2200', 10).build()))

    @no_duplicates
    def test_option_buy_to_open_limit(self):
        self.assertFalse(has_diff({
            'orderType': 'LIMIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '32.50',
            'orderLegCollection': [{
                'instruction': 'BUY_TO_OPEN',
                'quantity': 10,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }]
        }, option_buy_to_open_limit('GOOG_012122P2200', 10, '32.50').build()))

    # Sell to open

    @no_duplicates
    def test_option_sell_to_open_market(self):
        self.assertFalse(has_diff({
            'orderType': 'MARKET',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'SELL_TO_OPEN',
                'quantity': 10,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }]
        }, option_sell_to_open_market('GOOG_012122P2200', 10).build()))

    @no_duplicates
    def test_option_sell_to_open_limit(self):
        self.assertFalse(has_diff({
            'orderType': 'LIMIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '32.50',
            'orderLegCollection': [{
                'instruction': 'SELL_TO_OPEN',
                'quantity': 10,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }]
        }, option_sell_to_open_limit('GOOG_012122P2200', 10, '32.50').build()))

    # Buy to close

    @no_duplicates
    def test_option_buy_to_close_market(self):
        self.assertFalse(has_diff({
            'orderType': 'MARKET',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'BUY_TO_CLOSE',
                'quantity': 10,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }]
        }, option_buy_to_close_market('GOOG_012122P2200', 10).build()))

    @no_duplicates
    def test_option_buy_to_close_limit(self):
        self.assertFalse(has_diff({
            'orderType': 'LIMIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '32.50',
            'orderLegCollection': [{
                'instruction': 'BUY_TO_CLOSE',
                'quantity': 10,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }]
        }, option_buy_to_close_limit('GOOG_012122P2200', 10, '32.50').build()))

    # Sell to close

    @no_duplicates
    def test_option_sell_to_close_market(self):
        self.assertFalse(has_diff({
            'orderType': 'MARKET',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'SELL_TO_CLOSE',
                'quantity': 10,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }]
        }, option_sell_to_close_market('GOOG_012122P2200', 10).build()))

    @no_duplicates
    def test_option_sell_to_close_limit(self):
        self.assertFalse(has_diff({
            'orderType': 'LIMIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '32.50',
            'orderLegCollection': [{
                'instruction': 'SELL_TO_CLOSE',
                'quantity': 10,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }]
        }, option_sell_to_close_limit('GOOG_012122P2200', 10, '32.50').build()))



class VerticalTemplatesTest(unittest.TestCase):

    @no_duplicates
    def test_bull_call_vertical_open(self):
        self.assertFalse(has_diff({
            'orderType': 'NET_DEBIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '30.60',
            'complexOrderStrategyType': 'VERTICAL',
            'quantity': 3,
            'orderLegCollection': [{
                'instruction': 'BUY_TO_OPEN',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122C2200',
                    'assetType': 'OPTION',
                }
            }, {
                'instruction': 'SELL_TO_OPEN',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122C2400',
                    'assetType': 'OPTION',
                }
            }]
        }, bull_call_vertical_open(
            'GOOG_012122C2200',
            'GOOG_012122C2400',
            3, '30.60').build()))

    @no_duplicates
    def test_bull_call_vertical_close(self):
        self.assertFalse(has_diff({
            'orderType': 'NET_CREDIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '30.60',
            'complexOrderStrategyType': 'VERTICAL',
            'quantity': 3,
            'orderLegCollection': [{
                'instruction': 'SELL_TO_CLOSE',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122C2200',
                    'assetType': 'OPTION',
                }
            }, {
                'instruction': 'BUY_TO_CLOSE',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122C2400',
                    'assetType': 'OPTION',
                }
            }]
        }, bull_call_vertical_close(
            'GOOG_012122C2200',
            'GOOG_012122C2400',
            3, '30.60').build()))

    @no_duplicates
    def test_bear_call_vertical_open(self):
        self.assertFalse(has_diff({
            'orderType': 'NET_CREDIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '30.60',
            'complexOrderStrategyType': 'VERTICAL',
            'quantity': 3,
            'orderLegCollection': [{
                'instruction': 'SELL_TO_OPEN',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122C2200',
                    'assetType': 'OPTION',
                }
            }, {
                'instruction': 'BUY_TO_OPEN',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122C2400',
                    'assetType': 'OPTION',
                }
            }]
        }, bear_call_vertical_open(
            'GOOG_012122C2200',
            'GOOG_012122C2400',
            3, '30.60').build()))

    @no_duplicates
    def test_bear_call_vertical_close(self):
        self.assertFalse(has_diff({
            'orderType': 'NET_DEBIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '30.60',
            'complexOrderStrategyType': 'VERTICAL',
            'quantity': 3,
            'orderLegCollection': [{
                'instruction': 'BUY_TO_CLOSE',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122C2200',
                    'assetType': 'OPTION',
                }
            }, {
                'instruction': 'SELL_TO_CLOSE',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122C2400',
                    'assetType': 'OPTION',
                }
            }]
        }, bear_call_vertical_close(
            'GOOG_012122C2200',
            'GOOG_012122C2400',
            3, '30.60').build()))

    @no_duplicates
    def test_bull_put_vertical_open(self):
        self.assertFalse(has_diff({
            'orderType': 'NET_CREDIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '30.60',
            'complexOrderStrategyType': 'VERTICAL',
            'quantity': 3,
            'orderLegCollection': [{
                'instruction': 'BUY_TO_OPEN',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }, {
                'instruction': 'SELL_TO_OPEN',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122P2400',
                    'assetType': 'OPTION',
                }
            }]
        }, bull_put_vertical_open(
            'GOOG_012122P2200',
            'GOOG_012122P2400',
            3, '30.60').build()))

    @no_duplicates
    def test_bull_put_vertical_close(self):
        self.assertFalse(has_diff({
            'orderType': 'NET_DEBIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '30.60',
            'complexOrderStrategyType': 'VERTICAL',
            'quantity': 3,
            'orderLegCollection': [{
                'instruction': 'SELL_TO_CLOSE',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }, {
                'instruction': 'BUY_TO_CLOSE',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122P2400',
                    'assetType': 'OPTION',
                }
            }]
        }, bull_put_vertical_close(
            'GOOG_012122P2200',
            'GOOG_012122P2400',
            3, '30.60').build()))

    @no_duplicates
    def test_bear_put_vertical_open(self):
        self.assertFalse(has_diff({
            'orderType': 'NET_DEBIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '30.60',
            'complexOrderStrategyType': 'VERTICAL',
            'quantity': 3,
            'orderLegCollection': [{
                'instruction': 'SELL_TO_OPEN',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }, {
                'instruction': 'BUY_TO_OPEN',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122P2400',
                    'assetType': 'OPTION',
                }
            }]
        }, bear_put_vertical_open(
            'GOOG_012122P2200',
            'GOOG_012122P2400',
            3, '30.60').build()))

    @no_duplicates
    def test_bear_put_vertical_close(self):
        self.assertFalse(has_diff({
            'orderType': 'NET_CREDIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': '30.60',
            'complexOrderStrategyType': 'VERTICAL',
            'quantity': 3,
            'orderLegCollection': [{
                'instruction': 'BUY_TO_CLOSE',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122P2200',
                    'assetType': 'OPTION',
                }
            }, {
                'instruction': 'SELL_TO_CLOSE',
                'quantity': 3,
                'instrument': {
                    'symbol': 'GOOG_012122P2400',
                    'assetType': 'OPTION',
                }
            }]
        }, bear_put_vertical_close(
            'GOOG_012122P2200',
            'GOOG_012122P2400',
            3, '30.60').build()))


