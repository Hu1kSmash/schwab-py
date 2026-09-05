'''Tests for setup.py's metadata.

setup.py is not imported by anything else in the suite, so a syntax error or a
mistake in the dependency lists is invisible until someone runs a build or a
`pip install`. That happened: an edit to this file left it unparseable while
the whole suite stayed green.

These assertions are about relationships between the lists rather than their
contents, so adding a package does not require editing a test.
'''

import contextlib
import os
import re
import tempfile
import unittest
from unittest.mock import patch

import setuptools

from .utils import no_duplicates


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SETUP_PY = os.path.join(REPO_ROOT, 'setup.py')


@contextlib.contextmanager
def in_repo_root():
    '''setup.py opens README.rst and schwab/version.py by relative path, the
    way pip runs it. Every other test here is independent of the working
    directory and this one has to be too, so run it where it expects to be
    rather than from wherever pytest was invoked.'''
    previous = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        yield
    finally:
        os.chdir(previous)


def setup_kwargs():
    '''Runs setup.py with setuptools.setup captured rather than executed.'''
    captured = {}

    with in_repo_root():
        with open(SETUP_PY) as f:
            source = f.read()

        with patch.object(setuptools, 'setup', captured.update):
            exec(compile(source, SETUP_PY, 'exec'),
                 {'__name__': '__main__', 'setuptools': setuptools})

    return captured


def package_name(requirement):
    '''"websockets>=14.0" -> "websockets". Applied to both sides of every
    comparison below: normalising only one side made
    test_no_extra_is_in_install_requires pass for exactly the case it exists to
    catch, since a pinned duplicate in an extra would not match a bare name.'''
    for separator in ('>', '<', '=', '!', '~', '[', ';', ' '):
        requirement = requirement.split(separator)[0]
    return requirement.strip()


class SetupPyTest(unittest.TestCase):

    def setUp(self):
        self.kwargs = setup_kwargs()

    @no_duplicates
    def test_setup_py_parses_and_calls_setup(self):
        self.assertIn('name', self.kwargs)
        # The distribution is `schwaby`; the importable package is still
        # `schwab`. Asserted because they differ deliberately and a future
        # edit aligning them would be a breaking change for every consumer.
        self.assertEqual('schwaby', self.kwargs['name'])

    @no_duplicates
    def test_the_version_matches_the_package(self):
        from schwab.version import version
        self.assertEqual(version, self.kwargs['version'])

    @no_duplicates
    def test_install_requires_is_the_agreed_set(self):
        # Anything here lands on every machine running this library, so it
        # should be a deliberate decision rather than a merge artifact. The
        # login packages moved back in 2.7.0 after the extras split saved
        # twelve packages for nobody and cost three silent failure modes.
        names = sorted(package_name(r)
                       for r in self.kwargs['install_requires'])
        self.assertEqual(
                ['authlib', 'flask', 'httpx2', 'multiprocess', 'psutil',
                 'websockets'], names)

    @no_duplicates
    def test_the_extras_survive_as_no_ops(self):
        # Kept so an existing `schwaby[login]` pin installs without a pip
        # warning. Empty because everything they named is a hard dependency
        # now. Removing the names would break nobody's install but would print
        # 'does not provide the extra', which reads like a fault.
        extras = self.kwargs['extras_require']
        self.assertEqual([], extras['login'])
        self.assertEqual([], extras['codegen'])

    # The two checks below are vacuous against setup.py as it stands, because
    # every non-dev extra is empty: a subset test and a disjointness test both
    # hold for [] no matter what the other side contains. They would pass on a
    # `dev` list emptied by a bad merge, which is the exact failure the first
    # one exists to catch.
    #
    # So each is a function tested twice -- once against setup.py, and once
    # against a fixture that violates it. The second is the positive control.
    # Without it the assertions look like protection and are not, which is
    # worse than not having them. They are kept rather than deleted because the
    # extras are still declared and an extra with contents is one edit away.

    @staticmethod
    def extras_missing_from_dev(extras):
        dev = set(package_name(r) for r in extras.get('dev', ()))
        return sorted(name for name, packages in extras.items()
                      if name != 'dev'
                      and not set(package_name(r) for r in packages) <= dev)

    @staticmethod
    def extras_duplicating_install_requires(install_requires, extras):
        hard = set(package_name(r) for r in install_requires)
        return sorted(name for name, packages in extras.items()
                      if name != 'dev'
                      and set(package_name(r) for r in packages) & hard)

    @no_duplicates
    def test_dev_covers_every_extra(self):
        # The suite really starts flask servers through multiprocess, so a
        # package in an extra but missing from dev is a green local run against
        # a stale virtualenv and a red CI.
        self.assertEqual(
                [], self.extras_missing_from_dev(self.kwargs['extras_require']))

    @no_duplicates
    def test_dev_coverage_check_catches_a_gap(self):
        self.assertEqual(
                ['login'],
                self.extras_missing_from_dev({'login': ['flask'],
                                              'codegen': [],
                                              'dev': ['pytest']}))

    @no_duplicates
    def test_no_extra_is_in_install_requires(self):
        # An extra which repeats a hard dependency is a package that can never
        # be absent, advertised as optional.
        self.assertEqual(
                [],
                self.extras_duplicating_install_requires(
                    self.kwargs['install_requires'],
                    self.kwargs['extras_require']))

    @no_duplicates
    def test_duplicate_check_catches_a_duplicate(self):
        self.assertEqual(
                ['login'],
                self.extras_duplicating_install_requires(
                    ['flask', 'authlib>=1.8'],
                    {'login': ['flask'], 'codegen': [], 'dev': ['flask']}))


class ShippedFilesTest(unittest.TestCase):
    """What ends up in the wheel, and what the strings in it point at.

    `find_packages()` with no arguments matched `tests` as well as `schwab`,
    so every release through 2.6.0 shipped a top-level `tests` package into
    users' site-packages -- colliding file-for-file with anything else that
    ships one, and answering `import tests` from outside a project root.

    The URL check is the same class of problem seen from the other side.
    `auth.py` raised a ValueError pointing at `schwab-py.readthedocs.io`, the
    *original* project's documentation site, so a user who got a callback URL
    wrong was sent to read someone else's docs about a different codebase. It
    survived the rename because it is a string inside an error message, which
    no build step and no doc build looks at.

    That is an allowlist rather than a denylist. A denylist of the hosts
    already found is not a guard, it is a record: it cannot catch the next
    inherited link, and there was one -- `developer.schwabmeritrade.com` in
    `orders/generic.py`, a hostname that does not resolve, which a denylist
    naming only `schwab-py` hosts sailed straight past.
    """

    EXPECTED_PACKAGES = ['schwab', 'schwab.client', 'schwab.contrib',
                         'schwab.orders']

    # Every host a shipped string may name. Adding one is a deliberate act:
    # these are places we send users when something has already gone wrong, so
    # a stale or foreign entry is worse than no link at all.
    ALLOWED_HOSTS = frozenset((
        'github.com',                 # ours, and httpx2's changelog
        'api.schwabapi.com',          # the API itself
        'developer.schwab.com',       # Schwab's own documentation
        'docs.python.org',
        'websockets.readthedocs.io',  # a dependency's own docs
        'www.investopedia.com',       # order-type explanations in the enums
        'optionstradingiq.com',
    ))

    URL = re.compile(r'https?://([^/\s\'"`)>,]+)')

    @staticmethod
    def shipped_files():
        found = []
        for directory in ('schwab', 'bin'):
            root = os.path.join(REPO_ROOT, directory)
            for dirpath, _, filenames in os.walk(root):
                if '__pycache__' in dirpath:
                    continue
                for name in filenames:
                    if name.endswith('.py'):
                        found.append(os.path.join(dirpath, name))
        return found

    @classmethod
    def disallowed_hosts_in(cls, files):
        '''Returns (path, host) for every URL host outside ALLOWED_HOSTS.

        `files` is a parameter rather than a lookup so the positive control can
        run this same collection code over a fixture. A control which
        re-implements the predicate against a string literal proves only that
        the literal matches; it says nothing about whether the walk that feeds
        the real assertion found anything at all.
        '''
        offenders = []
        for path in files:
            with open(path, encoding='utf-8') as f:
                contents = f.read()
            for host in cls.URL.findall(contents):
                # Loopback, with or without a port: the callback server, not a
                # link anybody follows.
                if host.split(':')[0] == '127.0.0.1':
                    continue
                if host not in cls.ALLOWED_HOSTS:
                    offenders.append(
                            (os.path.relpath(path, REPO_ROOT), host))
        return sorted(offenders)

    @no_duplicates
    def test_only_schwab_packages_are_shipped(self):
        with in_repo_root():
            found = setuptools.find_packages(include=['schwab', 'schwab.*'])
        self.assertEqual(self.EXPECTED_PACKAGES, sorted(found))

    @no_duplicates
    def test_setup_py_ships_that_package_list(self):
        # The assertion above is about find_packages. This one is about what
        # setup.py actually passes, which is the thing that ends up in a wheel.
        self.assertEqual(self.EXPECTED_PACKAGES,
                         sorted(setup_kwargs()['packages']))

    @no_duplicates
    def test_no_disallowed_url_hosts(self):
        files = self.shipped_files()

        # Positive control for the walk. assertEqual([], offenders) holds just
        # as well when shipped_files() returned nothing -- a mistyped root, or
        # a future shipped directory that is not named in it.
        self.assertGreater(len(files), 10)
        self.assertIn(os.path.join(REPO_ROOT, 'schwab', 'auth.py'), files)

        self.assertEqual([], self.disallowed_hosts_in(files))

    @no_duplicates
    def test_the_check_catches_a_foreign_host(self):
        # Through the same collection code, not a re-implementation of it. Both
        # hosts below really were in this tree: the readthedocs link the check
        # was first written for, and the dead schwabmeritrade hostname that a
        # denylist of the first would have missed.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'shipped.py')
            with open(path, 'w') as f:
                f.write('See https://schwab-py.readthedocs.io/en/latest/ and\n'
                        'https://developer.schwabmeritrade.com/orders and\n'
                        'https://github.com/Hu1kSmash/schwaby\n')

            offenders = self.disallowed_hosts_in([path])

        self.assertEqual(['developer.schwabmeritrade.com',
                          'schwab-py.readthedocs.io'],
                         sorted(host for _, host in offenders))
