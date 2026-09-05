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


class ShippedProjectReferencesTest(unittest.TestCase):
    '''Strings in the installed package that name a project by URL.

    These are user-facing and nothing else checks them. `auth.py` raised a
    ValueError pointing at `schwab-py.readthedocs.io` --- the *original*
    project's documentation site, inherited and never updated --- so a user who
    got a callback URL wrong was sent to read someone else's docs about a
    different codebase. It survived the rename because it is a string inside an
    error message, which no build step and no doc build looks at.

    The test greps for the shape rather than that one instance: any
    documentation host in shipped code has to be one this project controls.
    '''

    # `alexgolec/schwab-py` is deliberately not here. Naming the origin project
    # in prose is correct and the README, CHANGELOG and docs all do it. What is
    # wrong is *sending a user there for instructions*, which only a docs host
    # does.
    FOREIGN_DOC_HOSTS = (
            'schwab-py.readthedocs.io',
            'schwab-py.rtfd.io',
    )

    def shipped_files(self):
        for directory in ('schwab', 'bin'):
            root = os.path.join(REPO_ROOT, directory)
            for dirpath, _, filenames in os.walk(root):
                if '__pycache__' in dirpath:
                    continue
                for name in filenames:
                    if name.endswith('.py'):
                        yield os.path.join(dirpath, name)

    @no_duplicates
    def test_no_foreign_documentation_hosts(self):
        offenders = []
        for path in self.shipped_files():
            with open(path, encoding='utf-8') as f:
                contents = f.read()
            for host in self.FOREIGN_DOC_HOSTS:
                if host in contents:
                    offenders.append(
                            '{}: {}'.format(os.path.relpath(path, REPO_ROOT),
                                            host))
        self.assertEqual([], offenders)

    @no_duplicates
    def test_the_check_would_have_caught_the_instance_it_was_written_for(self):
        # Red-proofing, kept rather than described: the assertion above passes
        # on an empty repository too, so it proves nothing on its own.
        contents = ("raise ValueError('See https://schwab-py.readthedocs.io/"
                    "en/latest/auth.html for more information')")
        self.assertTrue(any(host in contents
                            for host in self.FOREIGN_DOC_HOSTS))
