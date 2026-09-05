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

    @no_duplicates
    def test_dev_covers_every_extra(self):
        # The suite really starts flask servers through multiprocess, so a
        # package in an extra but missing from dev is a green local run against
        # a stale virtualenv and a red CI.
        extras = self.kwargs['extras_require']
        dev = set(package_name(r) for r in extras['dev'])

        for name, packages in extras.items():
            if name == 'dev':
                continue
            self.assertLessEqual(
                    set(package_name(r) for r in packages), dev,
                    '%r has packages missing from dev' % name)

    @no_duplicates
    def test_no_extra_is_in_install_requires(self):
        install_requires = set(
                package_name(r) for r in self.kwargs['install_requires'])

        for name, packages in self.kwargs['extras_require'].items():
            if name == 'dev':
                continue
            self.assertEqual(
                    set(), set(package_name(r) for r in packages)
                    & install_requires,
                    '%r duplicates a hard dependency' % name)
