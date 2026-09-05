'''Tests for setup.py's metadata.

setup.py is not imported by anything else in the suite, so a syntax error or a
mistake in the dependency lists is invisible until someone runs a build or a
`pip install`. That happened: an edit to this file left it unparseable while
the whole suite stayed green.

These assertions are about relationships between the lists rather than their
contents, so adding a package does not require editing a test.
'''

import collections
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
        # login packages moved back in 3.0.0 after the extras split saved
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
    """What ends up in the wheel.

    `find_packages()` with no arguments matched `tests` as well as `schwab`, so
    every release through 2.6.0 shipped a top-level `tests` package into users'
    site-packages -- colliding file-for-file with anything else that ships one,
    and answering `import tests` from outside a project root.
    """

    EXPECTED_PACKAGES = ['schwab', 'schwab.client', 'schwab.contrib',
                         'schwab.orders']

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


class LinkTest(unittest.TestCase):
    """Every URL a reader can follow, from shipped code and from the docs.

    Links rot in two ways and both have happened here.

    A whole host dies. `auth.py` raised a ValueError pointing at
    `schwab-py.readthedocs.io` --- the *original* project's docs, so a user who
    got a callback URL wrong was sent to read about a different codebase.
    `orders/generic.py` pointed at `developer.schwabmeritrade.com`, from the TD
    Ameritrade era, which does not resolve. `getting-started.rst` sent a new
    reader to `beta-developer.schwab.com` to register their app --- the first
    click in the whole onboarding flow, at a hostname that does not resolve.

    All three were found one at a time, and the first guard against them was a
    denylist of the hosts already caught, walking only `schwab/` and `bin/`.
    That is a record, not a check: it could not catch the next one, and the
    next one was in `docs/`, which is where the clickable links actually are.
    So this is an allowlist, over every file a reader's link can come from.

    Or the host survives and the target moves. Five of our own links are
    `github.com/.../blob/main/<path>` deep links, one of them an anchor into a
    section title. Renaming the file or retitling the section leaves the host
    unchanged, so a host check stays green while the link 404s or lands
    mid-page. Those are resolved against the working tree instead.
    """

    ALLOWED_HOSTS = frozenset((
        'github.com',                       # ours, plus httpx2's changelog
        'api.schwabapi.com',                # the API itself
        'developer.schwab.com',             # Schwab's own portal
        'www.schwab.com',
        'docs.python.org',
        'pypi.org',
        'pandas.pydata.org',
        'websockets.readthedocs.io',        # dependencies' own docs
        'requests-oauthlib.readthedocs.io',
        'virtualenv.pypa.io',
        'www.sphinx-doc.org',               # a comment in docs/conf.py
        'www.investopedia.com',             # order-type explanations
        'optionstradingiq.com',
        'www.cboe.com',
        'www.sec.gov',
        'www.businessinsider.com',
    ))

    # Hostnames that appear only inside example code, where they stand for a
    # value the reader replaces. They are not links and nobody clicks them.
    EXAMPLE_HOSTS = frozenset(('127.0.0.1', 'localhost', 'callback.com'))

    OURS = 'https://github.com/Hu1kSmash/schwaby/blob/main/'

    URL = re.compile(r'https?://([^/\s\'"`)>,]+)')
    OUR_LINK = re.compile(
            r'https://github\.com/Hu1kSmash/schwaby/blob/main/'
            r'([A-Za-z0-9_./-]+?)(?:#([a-z0-9-]+))?(?=[\s\'"`)>,]|$)')

    # `'…schwaby/' + 'blob/main/…'` is one URL to a reader and two string
    # literals to a regex. Both ValueError links in this library are written
    # that way, so the deep-link check silently covered neither -- which a
    # red-proof caught only because pointing one at a missing file changed
    # nothing. Joining adjacent literals first can merge two unrelated strings
    # into something URL-shaped, but that direction fails loudly; the other one
    # is a guard that quietly does nothing.
    ADJACENT_LITERALS = re.compile(r'[\'"]\s*\+?\s*[\'"]')

    @classmethod
    def read_joined(cls, path):
        with open(path, encoding='utf-8') as f:
            contents = f.read()
        if path.endswith('.py'):
            return cls.ADJACENT_LITERALS.sub('', contents)
        return contents

    @staticmethod
    def linkable_files():
        """Everything a reader's link can come out of: shipped code and docs.

        The first version of this walked `schwab/` and `bin/` only, which left
        the docs tree -- the place links are actually written -- uncovered, and
        a dead onboarding hostname sat there through it.
        """
        found = []
        for directory in ('schwab', 'bin', 'docs'):
            root = os.path.join(REPO_ROOT, directory)
            for dirpath, _, filenames in os.walk(root):
                if '__pycache__' in dirpath or '_build' in dirpath:
                    continue
                for name in filenames:
                    if name.endswith(('.py', '.rst')):
                        found.append(os.path.join(dirpath, name))
        found.append(os.path.join(REPO_ROOT, 'README.rst'))
        return found

    @classmethod
    def disallowed_hosts_in(cls, files):
        """Returns (path, host) for every URL host outside the allowlist.

        `files` is a parameter rather than a lookup so the positive control can
        run this same collection code over a fixture. A control that
        re-implements the predicate against a string literal proves only that
        the literal matches; it says nothing about whether the walk feeding the
        real assertion found anything at all.
        """
        offenders = []
        for path in files:
            contents = cls.read_joined(path)
            for host in cls.URL.findall(contents):
                if host.split(':')[0] in cls.EXAMPLE_HOSTS:
                    continue
                if host not in cls.ALLOWED_HOSTS:
                    offenders.append((os.path.relpath(path, REPO_ROOT), host))
        return sorted(set(offenders))

    @staticmethod
    def rst_anchors(path):
        """GitHub's slugs for the section titles in an .rst file.

        A title is a line with a punctuation underline of at least its own
        length beneath it. GitHub lowercases, drops anything that is not a word
        character, space or hyphen, and turns spaces into hyphens.
        """
        lines = open(path, encoding='utf-8').read().split('\n')
        anchors = set()
        for i, line in enumerate(lines[:-1]):
            title, under = line.strip(), lines[i + 1].strip()
            if (title and len(under) >= len(title) and len(under) > 2
                    and len(set(under)) == 1
                    and under[0] in '=-~+^"\'`#*_:.'):
                slug = re.sub(r'[^\w\s-]', '', title.lower())
                anchors.add(re.sub(r'[\s_]+', '-', slug).strip('-'))
        return anchors

    @classmethod
    def broken_own_links_in(cls, files):
        """Returns (path, url, why) for our own deep links that do not resolve.

        A host check cannot see these: rename docs/auth.rst or retitle a
        section and the host is still github.com.
        """
        broken = []
        for path in files:
            contents = cls.read_joined(path)
            for target, fragment in cls.OUR_LINK.findall(contents):
                where = os.path.relpath(path, REPO_ROOT)
                absolute = os.path.join(REPO_ROOT, target)
                if not os.path.exists(absolute):
                    broken.append((where, target, 'no such file'))
                elif fragment and target.endswith('.rst'):
                    if fragment not in cls.rst_anchors(absolute):
                        broken.append(
                                (where, target + '#' + fragment,
                                 'no section with that anchor'))
        return sorted(set(broken))

    @no_duplicates
    def test_no_disallowed_url_hosts(self):
        files = self.linkable_files()

        # Positive control for the walk. assertEqual([], offenders) holds just
        # as well when linkable_files() found nothing -- a mistyped root, or a
        # future directory that is not named in it.
        self.assertGreater(len(files), 20)
        for expected in (os.path.join(REPO_ROOT, 'schwab', 'auth.py'),
                         os.path.join(REPO_ROOT, 'docs', 'getting-started.rst'),
                         os.path.join(REPO_ROOT, 'README.rst')):
            self.assertIn(expected, files)

        self.assertEqual([], self.disallowed_hosts_in(files))

    @no_duplicates
    def test_the_host_check_catches_a_foreign_host(self):
        # Through the same collection code, not a re-implementation of the
        # predicate. All three hosts really were in this tree.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'shipped.py')
            with open(path, 'w') as f:
                f.write('See https://schwab-py.readthedocs.io/en/latest/ and\n'
                        'https://developer.schwabmeritrade.com/orders and\n'
                        'https://beta-developer.schwab.com/ and\n'
                        'https://github.com/Hu1kSmash/schwaby and\n'
                        'https://127.0.0.1:8182\n')

            offenders = self.disallowed_hosts_in([path])

        self.assertEqual(['beta-developer.schwab.com',
                          'developer.schwabmeritrade.com',
                          'schwab-py.readthedocs.io'],
                         sorted(host for _, host in offenders))

    @no_duplicates
    def test_our_own_deep_links_resolve(self):
        files = self.linkable_files()
        self.assertGreater(len(files), 20)

        # Positive control: these assertions are about a list that is empty
        # when everything is fine, so prove the links were actually found.
        # auth.py carries the ValueError's anchored link.
        found = collections.Counter()
        for path in files:
            for target, _ in self.OUR_LINK.findall(self.read_joined(path)):
                found[target] += 1
        self.assertGreater(sum(found.values()), 3)

        # Named, because these two are the reason the check exists: both are
        # written as concatenated literals, and both went unseen until the
        # joining above. A count alone would have stayed green.
        self.assertIn('docs/auth.rst', found)
        self.assertIn('docs/order-templates.rst', found)

        self.assertEqual([], self.broken_own_links_in(files))

    @no_duplicates
    def test_the_link_check_catches_a_moved_target_and_a_retitled_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'shipped.py')
            with open(path, 'w') as f:
                f.write(self.OURS + 'docs/auth.rst#callback-url-requirements\n'
                        + self.OURS + 'docs/auth.rst#no-such-section\n'
                        + self.OURS + 'docs/deleted-file.rst\n')

            broken = self.broken_own_links_in([path])

        self.assertEqual(
                [('docs/auth.rst#no-such-section',
                  'no section with that anchor'),
                 ('docs/deleted-file.rst', 'no such file')],
                [(target, why) for _, target, why in broken])

    @no_duplicates
    def test_the_anchor_the_callback_error_points_at_exists(self):
        # Named on its own because it is the one a user reaches while already
        # in trouble: client_from_login_flow refused their callback URL.
        anchors = self.rst_anchors(os.path.join(REPO_ROOT, 'docs', 'auth.rst'))
        self.assertIn('callback-url-requirements', anchors)
