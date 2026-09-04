import json
import unittest
import sys

from schwab.contrib.orders import (
        construct_repeat_order, code_for_builder, UnrepeatableOrderError)

class ConstructRepeatOrderTest(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def assertBuilder(self, expected_json, builder):
        self.assertEqual(
                json.dumps(expected_json, indent=4, sort_keys=True),
                json.dumps(builder.build(), indent=4, sort_keys=True))

        def validate_syntax(code, globalz):
            split_code = code.split('\n')
            line_format = (
                    ' {' + ':{}d'.format(len(str(len(split_code)))) + '}   {}')
            print('Generated code:')
            print()
            print('\n'.join(line_format.format(line_num + 1, line)
                for line_num, line in enumerate(split_code)))
            try:
                exec(code, globalz)
            except SyntaxError as e:
                print()
                print(e)
                assert False, 'Syntax error from generated code'

        # With a variable name, validate the syntax and expect the output
        code = code_for_builder(builder, 'test_builder')
        globalz = {}
        validate_syntax(code, globalz)
        self.assertEqual(
                json.dumps(expected_json, indent=4, sort_keys=True),
                json.dumps(
                    globalz['test_builder'].build(), indent=4, sort_keys=True))

        # With no variable name, just validate the syntax
        code = code_for_builder(builder)
        validate_syntax(code, {})


    def test_market_equity_order(self):
        historical_order = json.loads('''{
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "MARKET",
            "complexOrderStrategyType": "NONE",
            "quantity": 1.0,
            "filledQuantity": 1.0,
            "remainingQuantity": 0.0,'''+
            # XXX: See comment in contrib.orders._FIELDS_AND_SETTERS
            #"destinationLinkName": "AUTO",
            '''"orderLegCollection": [
                {
                    "orderLegType": "EQUITY",
                    "legId": 1,
                    "instrument": {
                        "assetType": "EQUITY",
                        "cusip": "1234567890",
                        "symbol": "FAKE"
                    },
                    "instruction": "BUY",
                    "positionEffect": "OPENING",
                    "quantity": 1.0
                }
            ],
            "orderStrategyType": "SINGLE",
            "orderId": 987654321,
            "cancelable": false,
            "editable": false,
            "status": "FILLED",
            "enteredTime": "2021-01-01T12:01:00+0000",
            "closeTime": "2021-01-01T12:01:01+0000",
            "tag": "tag",
            "accountId": 19191919,
            "orderActivityCollection": [
                {
                    "activityType": "EXECUTION",
                    "executionType": "FILL",
                    "quantity": 1.0,
                    "orderRemainingQuantity": 0.0,
                    "executionLegs": [
                        {
                            "legId": 1,
                            "quantity": 1.0,
                            "mismarkedQuantity": 0.0,
                            "price": 999.99,
                            "time": "2021-01-01T12:01:01+0000"
                        }
                    ]
                }
            ]
        }''')

        repeat_order = construct_repeat_order(historical_order)

        self.assertBuilder({
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderType': 'MARKET',
            'complexOrderStrategyType': 'NONE',
            'quantity': 1.0,
            # 'destinationLinkName': 'AUTO',
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'BUY',
                'instrument': {
                    'assetType': 'EQUITY',
                    'symbol': 'FAKE'
                },
                'quantity': 1.0
            }]
        }, repeat_order)


    def test_missing_orderStrategyType(self):
        historical_order = json.loads('''{
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "MARKET",
            "complexOrderStrategyType": "NONE",
            "quantity": 1.0,
            "filledQuantity": 1.0,
            "remainingQuantity": 0.0,
            "destinationLinkName": "AUTO",
            "orderLegCollection": [
                {
                    "orderLegType": "EQUITY",
                    "legId": 1,
                    "instrument": {
                        "assetType": "EQUITY",
                        "cusip": "1234567890",
                        "symbol": "FAKE"
                    },
                    "instruction": "BUY",
                    "positionEffect": "OPENING",
                    "quantity": 1.0
                }
            ],
            "orderId": 987654321,
            "cancelable": false,
            "editable": false,
            "status": "FILLED",
            "enteredTime": "2021-01-01T12:01:00+0000",
            "closeTime": "2021-01-01T12:01:01+0000",
            "tag": "tag",
            "accountId": 19191919,
            "orderActivityCollection": [
                {
                    "activityType": "EXECUTION",
                    "executionType": "FILL",
                    "quantity": 1.0,
                    "orderRemainingQuantity": 0.0,
                    "executionLegs": [
                        {
                            "legId": 1,
                            "quantity": 1.0,
                            "mismarkedQuantity": 0.0,
                            "price": 999.99,
                            "time": "2021-01-01T12:01:01+0000"
                        }
                    ]
                }
            ]
        }''')

        with self.assertRaises(ValueError,
                msg='historical order is missing orderStrategyType'):
            construct_repeat_order(historical_order)


    def test_unknown_orderLegType(self):
        historical_order = json.loads('''{
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "MARKET",
            "complexOrderStrategyType": "NONE",
            "quantity": 1.0,
            "filledQuantity": 1.0,
            "remainingQuantity": 0.0,
            "destinationLinkName": "AUTO",
            "orderLegCollection": [
                {
                    "orderLegType": "BOGUS",
                    "legId": 1,
                    "instrument": {
                        "assetType": "EQUITY",
                        "cusip": "1234567890",
                        "symbol": "FAKE"
                    },
                    "instruction": "BUY",
                    "positionEffect": "OPENING",
                    "quantity": 1.0
                }
            ],
            "orderStrategyType": "SINGLE",
            "orderId": 987654321,
            "cancelable": false,
            "editable": false,
            "status": "FILLED",
            "enteredTime": "2021-01-01T12:01:00+0000",
            "closeTime": "2021-01-01T12:01:01+0000",
            "tag": "tag",
            "accountId": 19191919,
            "orderActivityCollection": [
                {
                    "activityType": "EXECUTION",
                    "executionType": "FILL",
                    "quantity": 1.0,
                    "orderRemainingQuantity": 0.0,
                    "executionLegs": [
                        {
                            "legId": 1,
                            "quantity": 1.0,
                            "mismarkedQuantity": 0.0,
                            "price": 999.99,
                            "time": "2021-01-01T12:01:01+0000"
                        }
                    ]
                }
            ]
        }''')

        with self.assertRaises(ValueError,
                msg='unknown orderLegType'):
            construct_repeat_order(historical_order)

    def test_unknown_orderLegType_codegen(self):
        historical_order = json.loads('''{
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "MARKET",
            "complexOrderStrategyType": "NONE",
            "quantity": 1.0,
            "filledQuantity": 1.0,
            "remainingQuantity": 0.0,
            "destinationLinkName": "AUTO",
            "orderLegCollection": [
                {
                    "orderLegType": "EQUITY",
                    "legId": 1,
                    "instrument": {
                        "assetType": "EQUITY",
                        "cusip": "1234567890",
                        "symbol": "FAKE"
                    },
                    "instruction": "BUY",
                    "positionEffect": "OPENING",
                    "quantity": 1.0
                }
            ],
            "orderStrategyType": "SINGLE",
            "orderId": 987654321,
            "cancelable": false,
            "editable": false,
            "status": "FILLED",
            "enteredTime": "2021-01-01T12:01:00+0000",
            "closeTime": "2021-01-01T12:01:01+0000",
            "tag": "tag",
            "accountId": 19191919,
            "orderActivityCollection": [
                {
                    "activityType": "EXECUTION",
                    "executionType": "FILL",
                    "quantity": 1.0,
                    "orderRemainingQuantity": 0.0,
                    "executionLegs": [
                        {
                            "legId": 1,
                            "quantity": 1.0,
                            "mismarkedQuantity": 0.0,
                            "price": 999.99,
                            "time": "2021-01-01T12:01:01+0000"
                        }
                    ]
                }
            ]
        }''')

        repeat_order = construct_repeat_order(historical_order)
        repeat_order._orderLegCollection[0]['instrument']._assetType = 'BOGUS'

        with self.assertRaises(ValueError, msg='unknown leg asset type'):
            code_for_builder(repeat_order)


    def test_limit_options_order(self):
        historical_order = json.loads('''{
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "LIMIT",
            "complexOrderStrategyType": "NONE",
            "quantity": 1.0,
            "filledQuantity": 1.0,
            "remainingQuantity": 0.0,'''+
            # XXX: See comment in contrib.orders._FIELDS_AND_SETTERS
            #"destinationLinkName": "AUTO",
            '''"price": 0.21,
            "orderLegCollection": [{
                "orderLegType": "OPTION",
                "legId": 1,
                "instrument": {
                    "assetType": "OPTION",
                    "cusip": "0SPY..RJ00309000",
                    "symbol": "SPY_061920P309",
                    "description": "SPY Jun 19 2020 309.0 Put",
                    "underlyingSymbol": "SPY"
                },
                "instruction": "SELL_TO_CLOSE",
                "positionEffect": "CLOSING",
                "quantity": 1.0
            }],
            "orderStrategyType": "SINGLE",
            "orderId": 987654321,
            "cancelable": false,
            "editable": false,
            "status": "FILLED",
            "enteredTime": "2021-01-01T12:01:00+0000",
            "closeTime": "2021-01-01T12:01:01+0000",
            "tag": "tag",
            "accountId": 19191919,
            "orderActivityCollection": [{
                "activityType": "EXECUTION",
                "executionType": "FILL",
                "quantity": 1.0,
                "orderRemainingQuantity": 0.0,
                "executionLegs": [{
                    "legId": 1,
                    "quantity": 1.0,
                    "mismarkedQuantity": 0.0,
                    "price": 0.21,
                    "time": "2021-01-01T12:01:01+0000"
                }]
            }]
	}''')

        repeat_order = construct_repeat_order(historical_order)

        self.assertBuilder({
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderType': 'LIMIT',
            'complexOrderStrategyType': 'NONE',
            'quantity': 1.0,
            #'destinationLinkName': 'AUTO',
            'price': 0.21,
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'SELL_TO_CLOSE',
                'instrument': {
                    'assetType': 'OPTION',
                    'symbol': 'SPY_061920P309'
                },
                'quantity': 1.0
            }]
        }, repeat_order)


    def test_complex_options_order(self):
        historical_order = json.loads('''{
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "NET_DEBIT",
            "complexOrderStrategyType": "BUTTERFLY",
            "quantity": 1.0,
            "filledQuantity": 1.0,
            "remainingQuantity": 0.0,'''+
            # XXX: See comment in contrib.orders._FIELDS_AND_SETTERS
            '''"destinationLinkName": "AUTO",
            "price": 0.03,
            "orderLegCollection": [
                {
                    "orderLegType": "OPTION",
                    "legId": 1,
                    "instrument": {
                        "assetType": "OPTION",
                        "cusip": "0SPY..F110409000",
                        "symbol": "SPY_060121C409",
                        "description": "SPY JUN 1 2021 409.0 Call"
                    },
                    "instruction": "BUY_TO_OPEN",
                    "positionEffect": "OPENING",
                    "quantity": 1.0
                },
                {
                    "orderLegType": "OPTION",
                    "legId": 2,
                    "instrument": {
                        "assetType": "OPTION",
                        "cusip": "0SPY..F110410000",
                        "symbol": "SPY_060121C410",
                        "description": "SPY JUN 1 2021 410.0 Call"
                    },
                    "instruction": "SELL_TO_OPEN",
                    "positionEffect": "OPENING",
                    "quantity": 2.0
                },
                {
                    "orderLegType": "OPTION",
                    "legId": 3,
                    "instrument": {
                        "assetType": "OPTION",
                        "cusip": "0SPY..F110411000",
                        "symbol": "SPY_060121C411",
                        "description": "SPY JUN 1 2021 411.0 Call"
                    },
                    "instruction": "BUY_TO_OPEN",
                    "positionEffect": "OPENING",
                    "quantity": 1.0
                }
            ],
            "orderStrategyType": "SINGLE",
            "orderId": 1919191919,
            "cancelable": false,
            "editable": false,
            "status": "FILLED",
            "enteredTime": "2021-05-12T14:39:58+0000",
            "closeTime": "2021-05-12T14:39:58+0000",
            "accountId": 700000007,
            "orderActivityCollection": [
                {
                    "activityType": "EXECUTION",
                    "executionType": "FILL",
                    "quantity": 1.0,
                    "orderRemainingQuantity": 0.0,
                    "executionLegs": [
                        {
                            "legId": 1,
                            "quantity": 1.0,
                            "mismarkedQuantity": 0.0,
                            "price": 8.24,
                            "time": "2021-05-12T14:39:58+0000"
                        },
                        {
                            "legId": 2,
                            "quantity": 2.0,
                            "mismarkedQuantity": 0.0,
                            "price": 7.585,
                            "time": "2021-05-12T14:39:58+0000"
                        },
                        {
                            "legId": 3,
                            "quantity": 1.0,
                            "mismarkedQuantity": 0.0,
                            "price": 6.96,
                            "time": "2021-05-12T14:39:58+0000"
                        }
                    ]
                }
            ]
        }
	''')

        repeat_order = construct_repeat_order(historical_order)

        self.assertBuilder({
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderType': 'NET_DEBIT',
            'complexOrderStrategyType': 'BUTTERFLY',
            'quantity': 1.0,
            #'destinationLinkName': 'AUTO',
            'price': 0.03,
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'BUY_TO_OPEN',
                'instrument': {
                    'assetType': 'OPTION',
                    'symbol': 'SPY_060121C409'
                },
                'quantity': 1.0
            }, {
                'instruction': 'SELL_TO_OPEN',
                'instrument': {
                    'assetType': 'OPTION',
                    'symbol': 'SPY_060121C410'
                },
                'quantity': 2.0
            }, {
                'instruction': 'BUY_TO_OPEN',
                'instrument': {
                    'assetType': 'OPTION',
                    'symbol': 'SPY_060121C411'
                },
                'quantity': 1.0
            }]
        }, repeat_order)


    def test_one_triggers_other(self):
        historical_order = json.loads('''{
            "session": "NORMAL",
            "duration": "GOOD_TILL_CANCEL",
            "orderType": "LIMIT",
            "complexOrderStrategyType": "NONE",
            "quantity": 2.0,
            "filledQuantity": 2.0,
            "remainingQuantity": 0.0,'''+
            # XXX: See comment in contrib.orders._FIELDS_AND_SETTERS
            #"destinationLinkName": "AUTO",
            '''"price": 3.6,
            "orderLegCollection": [
                {
                    "orderLegType": "OPTION",
                    "legId": 1,
                    "instrument": {
                        "assetType": "OPTION",
                        "cusip": "0AEO..HK10035000",
                        "symbol": "AEO_082021C35",
                        "description": "AEO AUG 20 2021 35.0 Call"
                    },
                    "instruction": "BUY_TO_OPEN",
                    "positionEffect": "OPENING",
                    "quantity": 2.0
                }
            ],
            "orderStrategyType": "TRIGGER",
            "orderId": 29292929,
            "cancelable": false,
            "editable": false,
            "status": "FILLED",
            "enteredTime": "2021-04-20T02:40:28+0000",
            "closeTime": "2021-04-20T13:31:53+0000",
            "accountId": 19191919,
            "orderActivityCollection": [
                {
                    "activityType": "EXECUTION",
                    "executionType": "FILL",
                    "quantity": 2.0,
                    "orderRemainingQuantity": 0.0,
                    "executionLegs": [
                        {
                            "legId": 1,
                            "quantity": 2.0,
                            "mismarkedQuantity": 0.0,
                            "price": 3.6,
                            "time": "2021-04-20T13:31:53+0000"
                        }
                    ]
                }
            ],
            "childOrderStrategies": [
                {
                    "session": "NORMAL",
                    "duration": "GOOD_TILL_CANCEL",
                    "orderType": "LIMIT",
                    "complexOrderStrategyType": "NONE",
                    "quantity": 2.0,
                    "filledQuantity": 2.0,
                    "remainingQuantity": 0.0,'''+
                    #"destinationLinkName": "NYSE",
                    '''"price": 3.7,
                    "orderLegCollection": [
                        {
                            "orderLegType": "OPTION",
                            "legId": 1,
                            "instrument": {
                                "assetType": "OPTION",
                                "cusip": "0AEO..HK10035000",
                                "symbol": "AEO_082021C35",
                                "description": "AEO AUG 20 2021 35.0 Call"
                            },
                            "instruction": "SELL_TO_CLOSE",
                            "positionEffect": "CLOSING",
                            "quantity": 2.0
                        }
                    ],
                    "orderStrategyType": "SINGLE",
                    "orderId": 22992992,
                    "cancelable": false,
                    "editable": false,
                    "status": "FILLED",
                    "enteredTime": "2021-04-20T02:40:28+0000",
                    "closeTime": "2021-04-29T15:02:53+0000",
                    "accountId": 19191919,
                    "orderActivityCollection": [
                        {
                            "activityType": "EXECUTION",
                            "executionType": "FILL",
                            "quantity": 2.0,
                            "orderRemainingQuantity": 0.0,
                            "executionLegs": [
                                {
                                    "legId": 1,
                                    "quantity": 2.0,
                                    "mismarkedQuantity": 0.0,
                                    "price": 3.7,
                                    "time": "2021-04-29T15:02:53+0000"
                                }
                            ]
                        }
                    ]
                }
            ]
        }''')

        repeat_order = construct_repeat_order(historical_order)

        self.assertBuilder({
            'session': 'NORMAL',
            'duration': 'GOOD_TILL_CANCEL',
            'orderType': 'LIMIT',
            'complexOrderStrategyType': 'NONE',
            'quantity': 2.0,
            #'destinationLinkName': 'AUTO',
            'orderStrategyType': 'TRIGGER',
            'price': 3.6,
            'orderLegCollection': [{
                'instruction': 'BUY_TO_OPEN',
                'instrument': {
                    'assetType': 'OPTION',
                    'symbol': 'AEO_082021C35'
                },
                'quantity': 2.0,
            }],
            'childOrderStrategies': [{
                'session': 'NORMAL',
                'duration': 'GOOD_TILL_CANCEL',
                'orderType': 'LIMIT',
                'complexOrderStrategyType': 'NONE',
                'quantity': 2.0,
                'price': 3.7,
                #'destinationLinkName': 'NYSE',
                'orderStrategyType': 'SINGLE',
                'orderLegCollection': [{
                    'instruction': 'SELL_TO_CLOSE',
                    'instrument': {
                        'assetType': 'OPTION',
                        'symbol': 'AEO_082021C35'
                    },
                    'quantity': 2.0,
                }]
            }]
        }, repeat_order)

    def test_oco_inside_oto(self):
        historical_order = json.loads('''{
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "LIMIT",
            "complexOrderStrategyType": "NONE",
            "quantity": 1.0,
            "filledQuantity": 0.0,
            "remainingQuantity": 1.0,'''+
            # XXX: See comment in contrib.orders._FIELDS_AND_SETTERS
            # "destinationLinkName": "AUTO",
            '''"price": 2.71,
            "orderLegCollection": [
                {
                    "orderLegType": "OPTION",
                    "legId": 1,
                    "instrument": {
                        "assetType": "OPTION",
                        "cusip": "0BIGC.JF10060000",
                        "symbol": "BIGC_101521C60",
                        "description": "BIGC OCT 15 2021 60.0 Call"
                    },
                    "instruction": "BUY_TO_OPEN",
                    "positionEffect": "OPENING",
                    "quantity": 1.0
                }
            ],
            "orderStrategyType": "TRIGGER",
            "orderId": 4403477551,
            "cancelable": true,
            "editable": false,
            "status": "QUEUED",
            "enteredTime": "2021-05-13T03:12:54+0000",
            "accountId": 123123123,
            "childOrderStrategies": [
                {
                    "orderStrategyType": "OCO",
                    "orderId": 4403477554,
                    "cancelable": true,
                    "editable": false,
                    "accountId": 123123123,
                    "childOrderStrategies": [
                        {
                            "session": "NORMAL",
                            "duration": "DAY",
                            "orderType": "LIMIT",
                            "complexOrderStrategyType": "NONE",
                            "quantity": 1.0,
                            "filledQuantity": 0.0,
                            "remainingQuantity": 1.0,'''+
                            # "destinationLinkName": "AUTO",
                            '''"orderLegCollection": [
                                {
                                    "orderLegType": "OPTION",
                                    "legId": 1,
                                    "instrument": {
                                        "assetType": "OPTION",
                                        "cusip": "0BIGC.JF10060000",
                                        "symbol": "BIGC_101521C60",
                                        "description": "BIGC OCT 15 2021 60.0 Call"
                                    },
                                    "instruction": "SELL_TO_CLOSE",
                                    "positionEffect": "CLOSING",
                                    "quantity": 1.0
                                }
                            ],
                            "orderStrategyType": "SINGLE",
                            "orderId": 4403477553,
                            "cancelable": true,
                            "editable": false,
                            "status": "ACCEPTED",
                            "enteredTime": "2021-05-13T03:12:54+0000",
                            "accountId": 12312312
                        },
                        {
                            "session": "NORMAL",
                            "duration": "DAY",
                            "orderType": "STOP",
                            "complexOrderStrategyType": "NONE",
                            "quantity": 1.0,
                            "filledQuantity": 0.0,
                            "remainingQuantity": 1.0,'''+
                            # "destinationLinkName": "AUTO",
                            '''"orderLegCollection": [
                                {
                                    "orderLegType": "OPTION",
                                    "legId": 1,
                                    "instrument": {
                                        "assetType": "OPTION",
                                        "cusip": "0BIGC.JF10060000",
                                        "symbol": "BIGC_101521C60",
                                        "description": "BIGC OCT 15 2021 60.0 Call"
                                    },
                                    "instruction": "SELL_TO_CLOSE",
                                    "positionEffect": "CLOSING",
                                    "quantity": 1.0
                                }
                            ],
                            "orderStrategyType": "SINGLE",
                            "orderId": 4403477554,
                            "cancelable": true,
                            "editable": false,
                            "status": "ACCEPTED",
                            "enteredTime": "2021-05-13T03:12:54+0000",
                            "accountId": 488435533
                        }
                    ]
                }
            ]
        }''')

        repeat_order = construct_repeat_order(historical_order)

        self.assertBuilder({
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderType': 'LIMIT',
            'complexOrderStrategyType': 'NONE',
            'quantity': 1.0,
            #'destinationLinkName': 'AUTO',
            'orderStrategyType': 'TRIGGER',
            'price': 2.71,
            'orderLegCollection': [{
                'instruction': 'BUY_TO_OPEN',
                'instrument': {
                    'assetType': 'OPTION',
                    'symbol': 'BIGC_101521C60'
                },
                'quantity': 1.0,
            }],
            'childOrderStrategies': [{
                'orderStrategyType': 'OCO',
                'childOrderStrategies': [{
                    'session': 'NORMAL',
                    'duration': 'DAY',
                    'orderType': 'LIMIT',
                    'complexOrderStrategyType': 'NONE',
                    'quantity': 1.0,
                    #'destinationLinkName': 'AUTO',
                    'orderStrategyType': 'SINGLE',
                    'orderLegCollection': [{
                        'instruction': 'SELL_TO_CLOSE',
                        'instrument': {
                            'assetType': 'OPTION',
                            'symbol': 'BIGC_101521C60',
                        },
                        'quantity': 1.0,
                    }]
                }, {
                    'session': 'NORMAL',
                    'duration': 'DAY',
                    'orderType': 'STOP',
                    'complexOrderStrategyType': 'NONE',
                    'quantity': 1.0,
                    #'destinationLinkName': 'AUTO',
                    'orderStrategyType': 'SINGLE',
                    'orderLegCollection': [{
                        'instruction': 'SELL_TO_CLOSE',
                        'instrument': {
                            'assetType': 'OPTION',
                            'symbol': 'BIGC_101521C60',
                        },
                        'quantity': 1.0,
                    }]
                }]
            }]
        }, repeat_order)


class UnrepeatableOrderTest(unittest.TestCase):
    """Schwab documents UNKNOWN as a value duration and orderType can come back
    as, and says explicitly it is not accepted as an input. Reconstructing such
    an order used to raise a bare KeyError from inside an enum lookup."""

    def order(self, **overrides):
        o = {
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderType': 'LIMIT',
            'orderStrategyType': 'SINGLE',
            'price': '1.00',
            'orderLegCollection': [{
                'orderLegType': 'EQUITY',
                'instruction': 'BUY',
                'quantity': 1,
                'instrument': {'assetType': 'EQUITY', 'symbol': 'AAPL'},
            }],
        }
        o.update(overrides)
        return o

    def test_unknown_duration_is_reported_clearly(self):
        with self.assertRaises(UnrepeatableOrderError) as cm:
            construct_repeat_order(self.order(duration='UNKNOWN'))
        self.assertEqual('duration', cm.exception.historical_field)
        self.assertEqual('UNKNOWN', cm.exception.value)

    def test_unknown_order_type_is_reported_clearly(self):
        with self.assertRaises(UnrepeatableOrderError) as cm:
            construct_repeat_order(self.order(orderType='UNKNOWN'))
        self.assertEqual('orderType', cm.exception.historical_field)

    def test_an_ordinary_order_still_reconstructs(self):
        builder = construct_repeat_order(self.order())
        self.assertEqual('LIMIT', builder.build()['orderType'])


class GeneratedCodeFidelityTest(unittest.TestCase):
    '''The generated code has to rebuild the order it was generated from.
    A price is the case where that can fail quietly: as of 2.1.0 the builder
    holds it as a string, and rendering it bare emitted a float literal, so
    running the generated code produced a different order from the one it
    described.'''

    def builder(self):
        from schwab.orders.common import (
                Duration, EquityInstruction, OrderStrategyType, OrderType,
                Session)
        from schwab.orders.generic import OrderBuilder

        return (OrderBuilder()
                .set_session(Session.NORMAL)
                .set_duration(Duration.DAY)
                .set_order_type(OrderType.LIMIT)
                .set_order_strategy_type(OrderStrategyType.SINGLE)
                .add_equity_leg(EquityInstruction.BUY, 'GOOG', 1)
                .set_price('19.99'))

    def test_a_string_price_stays_a_string(self):
        code = code_for_builder(self.builder())
        self.assertIn(".copy_price('19.99')", code)
        self.assertNotIn('.copy_price(19.99)', code)

    def test_the_generated_code_rebuilds_the_same_order(self):
        original = self.builder().build()
        code = code_for_builder(self.builder())

        # The generated code is imports followed by a bare builder
        # expression, so bind it to run it.
        namespace = {}
        exec(code.replace('OrderBuilder() \\', 'order = OrderBuilder() \\', 1),
             namespace)
        rebuilt = namespace['order'].build()

        self.assertEqual(original['price'], rebuilt['price'])
        self.assertIsInstance(rebuilt['price'], str)


class PriceLinkedOrderRoundTripTest(unittest.TestCase):
    '''A price-linked order expresses its price as an offset from something
    else, so the offset is the number that decides what it costs. Dropping it
    while keeping the basis and the type does not produce a partial order -- it
    produces a different one, and quietly.'''

    def order(self, **overrides):
        o = {
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderType': 'LIMIT',
            'orderStrategyType': 'SINGLE',
            'priceLinkBasis': 'MARK',
            'priceLinkType': 'PERCENT',
            'priceOffset': 2.5,
            'orderLegCollection': [{
                'orderLegType': 'EQUITY',
                'instruction': 'BUY',
                'quantity': 1.0,
                'instrument': {'assetType': 'EQUITY', 'symbol': 'AAPL'},
            }],
        }
        o.update(overrides)
        return o

    def test_price_offset_survives_the_round_trip(self):
        rebuilt = construct_repeat_order(self.order()).build()
        self.assertEqual(2.5, rebuilt.get('priceOffset'))

    def test_the_whole_price_link_trio_survives_together(self):
        # The offset going missing while its basis and type remain is the
        # shape that matters: the order still looks price-linked and is priced
        # differently.
        rebuilt = construct_repeat_order(self.order()).build()
        for field in ('priceLinkBasis', 'priceLinkType', 'priceOffset'):
            self.assertIn(field, rebuilt)

    def test_the_generated_code_sets_the_offset(self):
        code = code_for_builder(construct_repeat_order(self.order()))
        self.assertIn('set_price_offset', code)

    def test_the_stop_price_trio_is_unaffected(self):
        rebuilt = construct_repeat_order(self.order(
                stopPriceLinkBasis='MARK',
                stopPriceLinkType='PERCENT',
                stopPriceOffset=1.25)).build()
        self.assertEqual(1.25, rebuilt.get('stopPriceOffset'))
