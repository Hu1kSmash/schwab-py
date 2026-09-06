import sys
import tempfile
import warnings

from unittest.mock import MagicMock, patch


class PicklableResponse:
    '''Stands in for a response where the test really pickles.

    MagicMock is not picklable, so a round-trip test built on one can only ever
    call copy() -- which is in-process, and therefore not the thing the fix is
    about. Module level so pickle can find it by name.
    '''

    def __init__(self, marker='response'):
        self.marker = marker

    def __eq__(self, other):
        return (isinstance(other, PicklableResponse)
                and other.marker == self.marker)

from schwab.utils import (
    AccountHashMismatchException,
    MissingLocationHeaderError,
    OrderIdNotFoundError,
    SchwabError,
    UnrecognizedLocationError,
    UnsuccessfulOrderException,
    Utils,
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
        #
        # Walked, not listed. The first version named seven modules, so an
        # exception added to any module outside that list -- schwab.debug, say
        # -- was simply not looked at, and the test went on passing while the
        # guarantee it states stopped being true.
        import importlib, inspect, pkgutil
        import schwab

        # Seeded with `schwab` itself: walk_packages yields only SUBmodules,
        # and schwab/__init__.py already runs module-level code, so an
        # exception defined there would never be looked at. Verified by hand
        # rather than by mutation, because nothing in __init__.py raises today
        # so a mutation of the seed is green either way: with an exception
        # added there, the seeded walk fails and the unseeded one passes.
        #
        # onerror re-raises rather than defaulting to None, which silently
        # drops a subpackage out of the walk if one of its imports ever fails.
        # That one is defensive and cannot be exercised while every module
        # imports cleanly, which is the point of having it.
        def _boom(name):
            self.fail('could not import %s while walking' % name)

        modules, found, missing = ['schwab'], {}, []
        for info in pkgutil.walk_packages(schwab.__path__, 'schwab.',
                                          onerror=_boom):
            modules.append(info.name)
        for name in modules:
            module = importlib.import_module(name)
            for attr, obj in vars(module).items():
                if (inspect.isclass(obj) and issubclass(obj, BaseException)
                        and obj.__module__ == name):
                    found['%s.%s' % (name, attr)] = obj
                    if not issubclass(obj, SchwabError):
                        missing.append('%s.%s' % (name, attr))

        # Controls for the walk itself, since an empty walk satisfies the
        # assertion below. Name specific classes from three separate modules
        # rather than counting: a count survives a whole module dropping out.
        self.assertGreater(len(modules), 8)
        for expected in ('schwab.utils.OrderIdNotFoundError',
                         'schwab.auth.RedirectTimeoutError',
                         'schwab.streaming.ResponseTimeoutError',
                         'schwab.orders.common.InvalidOrderException'):
            self.assertIn(expected, found)

        self.assertEqual([], missing)

    @no_duplicates
    def test_schwab_error_is_not_claimed_to_cover_bare_value_errors(self):
        # The library raises plain ValueError for argument validation in about
        # thirty places, so `except SchwabError` is NOT everything it can
        # throw. This pins the BEHAVIOUR; it does not read the docstring, so it
        # cannot stop the wording drifting back on its own -- the assertion
        # below does that part.
        from schwab.orders.generic import OrderBuilder

        for label, bad in (('set_quantity(-1)',
                            lambda: OrderBuilder().set_quantity(-1)),
                           ('set_price(0.1)',
                            lambda: OrderBuilder().set_price(0.1))):
            with self.subTest(call=label):
                with self.assertRaises(ValueError) as cm:
                    bad()
                self.assertNotIsInstance(cm.exception, SchwabError)

        # Assert the positive statement rather than the absence of one
        # phrasing: "not everything" can be reworded a dozen ways, but the
        # docstring has to keep saying that builtin ValueError is still raised.
        # Skipped under -OO, where docstrings are stripped and __doc__ is None.
        if SchwabError.__doc__ is None:                  # pragma: no cover
            self.skipTest('docstrings stripped (-OO)')
        self.assertIn('ValueError', SchwabError.__doc__)
        self.assertIn('not', SchwabError.__doc__)

    @no_duplicates
    def test_every_exception_survives_a_process_boundary(self):
        # These carry the thing they are about as a leading positional and pass
        # only the message to BaseException, so the default reconstruction
        # called __init__ with the message alone: TypeError for most, and for
        # UnsuccessfulOrderException a copy that bound the message to
        # `response` and lost the message. Nothing in this library crosses a
        # process boundary with an exception; this is for callers who do -- a
        # ProcessPoolExecutor over placements -- where the one saying an order
        # is live on the wrong account must not arrive as a TypeError about
        # argument counts.
        import copy, importlib, inspect, pickle, pkgutil
        import schwab

        r = PicklableResponse
        samples = {
            'SchwabError': ('m',),          # the base is a class too
            'UnexpectedResponse': (r(), 'm'),
            'UnexpectedResponseCode': (r(), 'm'),
            'UnparsableMessage': ('raw', ValueError('x'), 'm'),
            # ('m',) alone binds to the offending value, not to BaseException,
            # so str() would be '' and the message assertion below would
            # compare '' to '' and pass regardless.
            'UnusableMessage': ('frame', 'm'),
            'ResponseTimeoutError': ('svc', 'cmd', 60, 'm'),
            'UnsuccessfulOrderException': (r(), 'm'),
            'OrderIdNotFoundError': (r(), None, 'm'),
            'MissingLocationHeaderError': (r(), None, 'm'),
            'UnrecognizedLocationError': (r(), 'loc', 'm'),
            'AccountHashMismatchException': (r(), 123, 'BBBB', 'm'),
            'TokenRefreshError': ('m',),
            'RedirectTimeoutError': ('m',),
            'RedirectServerExitedError': ('m',),
            'InvalidOrderException': ('m',),
        }

        # Seeded with `schwab` for the same reason as the walk above: an
        # exception defined in schwab/__init__.py is not a submodule, so it
        # would get no sample, never be round-tripped, and the count control
        # below would still pass because it counts only what the walk found.
        seen, modules = 0, ['schwab']
        modules.extend(i.name for i in pkgutil.walk_packages(
                schwab.__path__, 'schwab.',
                onerror=lambda n: self.fail('could not import %s' % n)))

        for name in modules:
            module = importlib.import_module(name)
            for attr, obj in vars(module).items():
                if not (inspect.isclass(obj) and issubclass(obj, BaseException)
                        and obj.__module__ == name):
                    continue
                self.assertIn(attr, samples, 'new exception, add a sample')
                seen += 1
                exc = obj(*samples[attr])
                with self.subTest(exception=attr):
                    # pickle is the one that matters -- copy is in-process, so
                    # a test built only on it does not cross a boundary at all.
                    for rebuilt in (copy.copy(exc), copy.deepcopy(exc),
                                    pickle.loads(pickle.dumps(exc))):
                        self.assertIs(type(rebuilt), obj)
                        self.assertEqual(str(exc), str(rebuilt))
                        self.assertNotEqual('', str(rebuilt))

        # The walk found them, rather than the loop never running.
        self.assertEqual(len(samples), seen)

    @no_duplicates
    def test_the_attributes_survive_it_too(self):
        # A message that survives while .order_id does not would be the same
        # bug wearing a different face: the handler is told an order is live
        # and cannot reach it.
        import copy, pickle
        response = PicklableResponse('the original')
        exc = AccountHashMismatchException(
                response, 987, 'BBBB', 'm', expected_account_hash='AAAA')

        for rebuilt in (copy.copy(exc), pickle.loads(pickle.dumps(exc))):
            self.assertEqual(987, rebuilt.order_id)
            self.assertEqual('BBBB', rebuilt.account_hash)
            self.assertEqual('AAAA', rebuilt.expected_account_hash)
            # The historical defect was not a LOST response but a WRONG one --
            # the message bound into the response slot. assertIsNotNone cannot
            # see that; equality can.
            self.assertEqual(response, rebuilt.response)
            self.assertEqual('m', str(rebuilt))

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

        with self.assertRaises(AccountHashMismatchException) as cm:
            self.utils.extract_order_id(response)

        # This fires only after the response came back successful AND an order
        # id parsed out of it, so an order really was placed -- on an account
        # the caller was not expecting to trade. Everything needed to go and
        # cancel it is on the exception rather than left in the message for
        # somebody to re-derive with a regex.
        self.assertEqual(123, cm.exception.order_id)
        self.assertEqual('badhash', cm.exception.account_hash)
        # Both hashes: a handler far from the call site has no Utils left to
        # ask which account it meant, and should not have to parse the message.
        self.assertEqual(self.utils.account_hash,
                         cm.exception.expected_account_hash)
        self.assertNotEqual(cm.exception.account_hash,
                            cm.exception.expected_account_hash)
        self.assertIs(response, cm.exception.response)
        self.assertIn('is live', str(cm.exception))

    @no_duplicates
    def test_the_mismatch_says_the_order_exists(self):
        # The old message was "order request account hash != Utils.account_hash",
        # and the docstring called it a wiring problem "rather than the order".
        # Both read as a configuration complaint. An order had been placed.
        response = MockResponse({}, 200, headers={
            'Location':
            'https://api.schwabapi.com/trader/v1/accounts/badhash/orders/123'})

        with self.assertRaises(AccountHashMismatchException) as cm:
            self.utils.extract_order_id(response)

        message = str(cm.exception)
        self.assertIn('123', message)        # which order
        self.assertIn('badhash', message)    # on which account

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


class CollisionWarningTest(unittest.TestCase):
    """`import schwab` warns when `schwab-py` is installed beside it.

    This cannot be caught earlier. pip does not implement `Conflicts-Dist` --
    its resolver never reads the field -- and a wheel runs no code when it is
    installed, by design. Import is the first moment the situation can be
    described at all.

    A warning and not an exception: the library places orders, the installed
    files usually work, and the damage comes from the *next* `pip uninstall`.
    Failing the import would break a running system to complain about a state
    that has not broken it yet.
    """

    def call_it(self, listing, files=()):
        '''Runs the check against a synthetic sys.path entry.

        `listing` is what os.listdir returns for it -- the real check is a
        directory scan, so that is the seam. `files` are created as plain
        files rather than directories, which is how a source tree is built:
        an entry holding `setup.py` is a checkout, not an install directory.
        '''
        import os
        import schwab

        with tempfile.TemporaryDirectory() as tmp:
            for name in listing:
                os.mkdir(os.path.join(tmp, name))
            for name in files:
                with open(os.path.join(tmp, name), 'w') as f:
                    f.write('')
            with patch.object(sys, 'path', [tmp]):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    schwab._warn_if_schwab_py_is_also_installed()
        return caught

    @no_duplicates
    def test_warns_when_both_are_installed(self):
        caught = self.call_it(
                ['schwab_py-2.5.1.dist-info', 'schwaby-3.0.1.dist-info'])

        self.assertEqual(1, len(caught))
        self.assertIs(RuntimeWarning, caught[0].category)
        message = str(caught[0].message)

        # The two things a reader has to come away with: do not run the
        # obvious cleanup, and here is what to run instead.
        self.assertIn('pip uninstall schwab-py', message)
        self.assertIn('pip uninstall -y schwab-py schwaby', message)

    @no_duplicates
    def test_silent_when_only_this_project_is_installed(self):
        self.assertEqual([], self.call_it(['schwaby-3.0.1.dist-info']))

    @no_duplicates
    def test_silent_when_schwab_py_is_this_project_under_its_old_name(self):
        # The case that matters most, because it is every checkout of this
        # repository made before 2.6.0: an editable install from that era
        # registers `schwab_py`, and nothing named `schwaby` exists beside it.
        # There is no second copy of anything, so there is nothing to say --
        # and a warning here would fire on every `pytest` run in the tree,
        # which is the fastest way to teach a reader to ignore it.
        for name in ('schwab_py-2.0.0.dist-info', 'schwab-py-2.5.1.dist-info'):
            with self.subTest(alone=name):
                self.assertEqual([], self.call_it([name]), name)

    @no_duplicates
    def test_silent_for_a_source_tree_build_artefact(self):
        # setuptools writes `<name>.egg-info` into a source tree as a build
        # artefact, and a checkout is on sys.path for every `pytest` run from
        # its root -- this repository's own `schwaby.egg-info` is one. Read as
        # an install it says "schwaby is installed here", which paired with a
        # stale `schwab_py` registration is a collision between the project
        # and itself.
        #
        # The discriminator is the directory: an install directory never holds
        # `setup.py` or `pyproject.toml`, and a checkout always does.
        self.assertEqual([], self.call_it(
                ['schwaby.egg-info', 'schwab_py-2.0.0.dist-info'],
                files=['setup.py']))

        # The positive control, and the thing that makes this a discriminator
        # rather than a blanket exclusion: the same two names in a directory
        # that is *not* a checkout are two real installs.
        self.assertEqual(1, len(self.call_it(
                ['schwaby.egg-info', 'schwab_py-2.0.0.dist-info'])))

    @no_duplicates
    def test_a_checkouts_own_dist_info_is_not_an_install_either(self):
        # `setup.py dist_info` writes a `.dist-info` into the checkout root,
        # so restricting the source-tree discriminator to `.egg-info` leaves
        # the same false positive reachable by a different artefact: the
        # project reported as colliding with itself.
        self.assertEqual([], self.call_it(
                ['schwaby-3.0.2.dist-info', 'schwab_py-2.0.0.dist-info'],
                files=['setup.py']))

        # Positive control: the same two names where there is no checkout.
        self.assertEqual(1, len(self.call_it(
                ['schwaby-3.0.2.dist-info', 'schwab_py-2.0.0.dist-info'])))

    @no_duplicates
    def test_egg_info_counts_outside_a_source_tree(self):
        # On a Debian or Ubuntu system interpreter the distro-packaged
        # modules register as `.egg-info` and nothing else does -- measured at
        # 73 against 35 `.dist-info` on this machine's `/usr/bin/python3`.
        # Skipping the layout outright would hide two thirds of what is
        # installed, and with it a legacy-installed `schwab-py`, which is
        # precisely the old install this check exists to find.
        for old_name in ('schwab_py-2.5.1.egg-info',
                         'schwab_py-2.5.1-py3.12.egg-info',
                         'schwab_py.egg-info'):
            with self.subTest(layout=old_name):
                self.assertEqual(1, len(self.call_it(
                        [old_name, 'schwaby-3.0.2.dist-info'])), old_name)

    @no_duplicates
    def test_a_nameless_dist_info_contributes_no_name(self):
        # A directory called exactly `.dist-info` leaves an empty stem. The
        # empty string could never equal either name we look for, so nothing
        # would misfire -- but the function is documented as returning the
        # names of the installed distributions, and `{''}` is not one.
        import os
        import schwab

        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, '.dist-info'))
            os.mkdir(os.path.join(tmp, 'schwaby-3.0.2.dist-info'))
            with patch.object(sys, 'path', [tmp]):
                names = schwab._installed_distribution_names()

        self.assertEqual({'schwaby'}, names)

    @no_duplicates
    def test_the_layouts_it_recognises(self):
        # The hyphen spelling as well as the normalised underscore one, and
        # versioned as well as not -- which appears depends on how each side
        # was installed, and old enough tooling wrote the name unescaped.
        pairs = (
            ('schwab_py-2.5.1.dist-info', 'schwaby-3.0.1.dist-info'),
            ('schwab-py-2.5.1.dist-info', 'schwaby-3.0.1.dist-info'),
            ('schwab.py-2.5.1.dist-info', 'schwaby-3.0.1.dist-info'),
            ('SCHWAB_PY-2.5.1.DIST-INFO', 'SCHWABY-3.0.1.DIST-INFO'),
            ('schwab_py.dist-info', 'schwaby.dist-info'),
            # The unversioned *hyphenated* spelling, which is the only shape
            # the digit test decides: `schwab-py`.rpartition('-') gives up
            # its `py` unless the tail is checked for a version.
            ('schwab-py.dist-info', 'schwaby.dist-info'),
            # The legacy `setup.py install` spelling, which carries the
            # interpreter version after the distribution version.
            ('schwab_py-2.5.1-py3.12.egg-info', 'schwaby-3.0.2.dist-info'),
        )
        for old, new in pairs:
            with self.subTest(layout=old):
                self.assertEqual(1, len(self.call_it([old, new])), old)

        # And things that merely start similarly must not trip it, however
        # they are paired.
        for name in ('schwab_pyx-1.0.dist-info', 'schwab_py_extras-1.0.dist-info',
                     'schwabypy-1.0.dist-info', 'schwab_py-2.5.1.txt'):
            with self.subTest(near_miss=name):
                self.assertEqual(
                        [], self.call_it([name, 'schwaby-3.0.1.dist-info']),
                        name)

    @no_duplicates
    def test_an_unreadable_entry_does_not_hide_a_later_one(self):
        # The inner `except OSError: continue` is not the same as letting the
        # outer guard catch it. Both keep the import alive, but only `continue`
        # keeps scanning -- and schwab-py may be on a later sys.path entry than
        # the directory that could not be read.
        import os
        import schwab

        real_listdir = os.listdir

        with tempfile.TemporaryDirectory() as good:
            os.mkdir(os.path.join(good, 'schwab_py-2.5.1.dist-info'))
            os.mkdir(os.path.join(good, 'schwaby-3.0.1.dist-info'))
            bad = os.path.join(good, 'nope')

            def listdir(entry):
                if entry == bad:
                    raise PermissionError(entry)
                return real_listdir(entry)

            with patch.object(os.path, 'isdir', lambda p: True):
                with patch.object(os, 'listdir', listdir):
                    with patch.object(sys, 'path', [bad, good]):
                        with warnings.catch_warnings(record=True) as caught:
                            warnings.simplefilter('always')
                            schwab._warn_if_schwab_py_is_also_installed()

        self.assertEqual(1, len(caught),
                         'an unreadable earlier entry hid a later match')

    @no_duplicates
    def test_the_two_halves_can_live_on_different_path_entries(self):
        # site-packages and a `--user` directory are two entries, and the
        # collision is exactly as real when the pair is split across them.
        import os
        import schwab

        with tempfile.TemporaryDirectory() as first:
            with tempfile.TemporaryDirectory() as second:
                os.mkdir(os.path.join(first, 'schwaby-3.0.1.dist-info'))
                os.mkdir(os.path.join(second, 'schwab_py-2.5.1.dist-info'))

                with patch.object(sys, 'path', [first, second]):
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        schwab._warn_if_schwab_py_is_also_installed()

        self.assertEqual(1, len(caught))

    @no_duplicates
    def test_warnings_as_errors_is_told_without_the_import_dying(self):
        # Two requirements that collide here. A warning must not be swallowed
        # by the `except Exception` guard -- that would leave the one
        # configuration that asked to be told loudest as the only one told
        # nothing. And the import must not fail, because under `-W error` a
        # warning raises, and a library that places orders should not die at
        # import over a condition where the files on disk still work.
        #
        # Both are satisfied by catching the raise and printing instead.
        import io
        import os
        import schwab

        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('schwab_py-2.5.1.dist-info',
                         'schwaby-3.0.2.dist-info'):
                os.mkdir(os.path.join(tmp, name))
            with patch.object(sys, 'path', [tmp]):
                with patch.object(sys, 'stderr', stderr):
                    with warnings.catch_warnings():
                        warnings.simplefilter('error')
                        # Must not raise.
                        schwab._warn_if_schwab_py_is_also_installed()

        printed = stderr.getvalue()
        self.assertIn('RuntimeWarning', printed)
        self.assertIn('pip uninstall -y schwab-py schwaby', printed)

    @no_duplicates
    def test_a_hostile_warning_system_cannot_kill_the_import(self):
        # `warnings.showwarning` is a documented replacement point and
        # daemonised hosts replace it. If the replacement raises something
        # that is not a `Warning`, a narrow `except Warning` misses it and the
        # import dies -- over a diagnostic, in a library that places orders.
        import io
        import os
        import schwab

        def hostile(*args, **kwargs):
            raise RuntimeError('this host does not do warnings')

        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('schwab_py-2.5.1.dist-info',
                         'schwaby-3.0.2.dist-info'):
                os.mkdir(os.path.join(tmp, name))
            with patch.object(sys, 'path', [tmp]):
                with patch.object(sys, 'stderr', stderr):
                    with warnings.catch_warnings():
                        warnings.simplefilter('always')
                        warnings.showwarning = hostile
                        # Must not raise.
                        schwab._warn_if_schwab_py_is_also_installed()

        self.assertIn('pip uninstall -y schwab-py schwaby',
                      stderr.getvalue())

    @no_duplicates
    def test_a_closed_stderr_cannot_kill_the_import_either(self):
        # The last resort. Both ways of saying it have failed, so there is
        # nowhere left to say it -- but the import still has to survive.
        import io
        import os
        import schwab

        closed = io.StringIO()
        closed.close()

        with tempfile.TemporaryDirectory() as tmp:
            for name in ('schwab_py-2.5.1.dist-info',
                         'schwaby-3.0.2.dist-info'):
                os.mkdir(os.path.join(tmp, name))
            with patch.object(sys, 'path', [tmp]):
                with patch.object(sys, 'stderr', closed):
                    with warnings.catch_warnings():
                        warnings.simplefilter('error')
                        # Must not raise.
                        schwab._warn_if_schwab_py_is_also_installed()

    @no_duplicates
    def test_a_detached_stderr_does_not_leak_into_stdout(self):
        # `sys.stderr` is None under pythonw and in hosts that detach it --
        # the same hosts that replace `showwarning`. `print(file=None)` falls
        # back to *stdout*, which would push a multi-line diagnostic into
        # whatever the program emits as data: a CLI writing JSON gets output
        # its caller cannot parse.
        import io
        import os
        import schwab

        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('schwab_py-2.5.1.dist-info',
                         'schwaby-3.0.2.dist-info'):
                os.mkdir(os.path.join(tmp, name))
            with patch.object(sys, 'path', [tmp]):
                with patch.object(sys, 'stderr', None):
                    with patch.object(sys, 'stdout', stdout):
                        with warnings.catch_warnings():
                            warnings.simplefilter('error')
                            # Must not raise.
                            schwab._warn_if_schwab_py_is_also_installed()

        self.assertEqual('', stdout.getvalue())

    @no_duplicates
    def test_nothing_is_printed_to_stderr_in_the_ordinary_case(self):
        # The positive control for the test above: the stderr path is the
        # fallback, not the mechanism. With default filters the warning goes
        # through `warnings` and stderr stays clean, so a passing assertion
        # there is not just "the check never ran".
        import io
        import os
        import schwab

        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('schwab_py-2.5.1.dist-info',
                         'schwaby-3.0.2.dist-info'):
                os.mkdir(os.path.join(tmp, name))
            with patch.object(sys, 'path', [tmp]):
                with patch.object(sys, 'stderr', stderr):
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        schwab._warn_if_schwab_py_is_also_installed()

        self.assertEqual(1, len(caught))
        self.assertEqual('', stderr.getvalue())

    @no_duplicates
    def test_a_broken_lookup_cannot_break_the_import(self):
        # A diagnostic that raises is worse than the thing it diagnoses, and
        # this one runs before anything else in the package.
        #
        # It has to be something other than OSError. `except OSError: continue`
        # inside the scan handles that one, so an unreadable directory never
        # reaches the outer guard and cannot prove it exists -- which is what
        # the earlier version of this test was doing.
        import os
        import schwab

        def explode(path):
            raise RuntimeError('os.path.isdir is not itself today')

        with patch.object(sys, 'path', ['/anything']):
            with patch.object(os.path, 'isdir', explode):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    schwab._warn_if_schwab_py_is_also_installed()  # no raise

        self.assertEqual([], caught)

    @no_duplicates
    def test_the_package_calls_it_on_import(self):
        # The check is only worth anything if it runs, and nothing else in the
        # suite would notice the call at the bottom of `schwab/__init__.py`
        # being deleted.
        import os

        source = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'schwab', '__init__.py')
        with open(source, encoding='utf-8') as f:
            body = f.read()

        self.assertIn('\n_warn_if_schwab_py_is_also_installed()\n', body)
