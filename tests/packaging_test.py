'''Tests for setup.py's metadata.

setup.py is not imported by anything else in the suite, so a syntax error or a
mistake in the dependency lists is invisible until someone runs a build or a
`pip install`. That happened: an edit to this file left it unparseable while
the whole suite stayed green.

These assertions are about relationships between the lists rather than their
contents, so adding a package does not require editing a test.
'''

import ast
import collections
import contextlib
import importlib
import inspect
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
        #
        # cryptography is here because the callback server runs with
        # ssl_context='adhoc' and werkzeug builds that certificate with it.
        # Nothing in flask's or werkzeug's metadata says so -- it arrives via
        # authlib today, which is a coincidence, not a guarantee.
        names = sorted(package_name(r)
                       for r in self.kwargs['install_requires'])
        self.assertEqual(
                ['authlib', 'cryptography', 'flask', 'httpx2', 'multiprocess',
                 'psutil', 'websockets'], names)

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
    # RFC 2606 reserves example.com for documentation, and loopback is the
    # callback server rather than a link. `callback.com` used to be here: a
    # real registrable domain standing in for one the reader supplies, which is
    # someone else's host to send a reader to.
    EXAMPLE_HOSTS = frozenset(('127.0.0.1', 'localhost'))
    EXAMPLE_SUFFIXES = ('.example.com', '.example.org', '.example.net')

    OURS = 'https://github.com/Hu1kSmash/schwaby/blob/main/'

    # `\s*` after the slashes is load-bearing. RST wraps long links, and
    # `getting-started.rst` had `<https://\nvirtualenv.pypa.io/...>` -- so a
    # host anchored straight to `//` never saw it. The tell was that
    # virtualenv.pypa.io was in the allowlist and no scanned file produced it.
    URL = re.compile(r'https?://\s*([^/\s\'"`)>,]+)')
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
            contents = cls.ADJACENT_LITERALS.sub('', contents)
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
        for name in sorted(os.listdir(REPO_ROOT)):
            if name.endswith(('.rst', '.md')):
                found.append(os.path.join(REPO_ROOT, name))
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
                bare = host.split(':')[0]
                if (bare in cls.EXAMPLE_HOSTS
                        or bare == 'example.com'
                        or bare.endswith(cls.EXAMPLE_SUFFIXES)):
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
                        'https://github.com/Hu1kSmash/schwaby and\n'
                        'https://127.0.0.1:8182\n')

            wrapped = os.path.join(tmp, 'wrapped.rst')
            with open(wrapped, 'w') as f:
                # The shape that slipped past: RST breaking a long link
                # immediately after the slashes.
                f.write('`the console <https://\n'
                        'beta-developer.schwab.com/dashboard>`__\n')

            offenders = self.disallowed_hosts_in([path, wrapped])

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


class DocsConfigTest(unittest.TestCase):
    """`docs/conf.py`'s project name, which titles every rendered page.

    It said `schwab-py` from the rename until 3.0.0 -- so every page title,
    browser tab and sidebar named the original project while the text on the
    page said to install `schwaby`. Nothing catches a name in a config file:
    the docs build does not care, and the link checks look at URLs.
    """

    @no_duplicates
    def test_sphinx_project_matches_the_distribution_name(self):
        namespace = {'__file__': os.path.join(REPO_ROOT, 'docs', 'conf.py')}
        with in_repo_root():
            with open(namespace['__file__']) as f:
                exec(compile(f.read(), 'conf.py', 'exec'), namespace)

        self.assertEqual(setup_kwargs()['name'], namespace['project'])

    @no_duplicates
    def test_the_author_credit_is_deliberately_not_checked(self):
        # `author` and `copyright` still name Alex Golec, which is correct and
        # must not be swept along by the assertion above. Stated as a test so
        # that changing it is a deliberate act rather than a tidy-up.
        namespace = {'__file__': os.path.join(REPO_ROOT, 'docs', 'conf.py')}
        with in_repo_root():
            with open(namespace['__file__']) as f:
                exec(compile(f.read(), 'conf.py', 'exec'), namespace)

        self.assertIn('Alex Golec', namespace['author'])
        self.assertIn('Alex Golec', namespace['copyright'])


class DocReferenceTest(unittest.TestCase):
    """Every name the documentation points at, resolved against the code.

    `streaming.rst` told readers to call `Client.search_instruments()` and gave
    a worked example using it. No such method exists -- it is `get_instruments`
    -- so anyone copying the example got an AttributeError. The reference was
    inherited and nothing noticed, because `sphinx -W` does not resolve a
    `:meth:` target to a real attribute: an unresolvable one renders as plain
    text and the build succeeds.

    Two forms have to be handled, and only handling the first is how this was
    missed the first time it was checked by hand:

        :meth:`schwab.client.Client.get_quote`
        :meth:`Client.get_quote() <schwab.client.Client.get_quote>`

    The second puts the real target inside the angle brackets, so a pattern
    that reads the visible label sees `Client.get_quote()` -- which does not
    start with `schwab`, gets skipped as somebody else's name, and the broken
    target behind it is never looked at.
    """

    ROLE = re.compile(r':(?:func|meth|class|attr|obj|data|exc):`([^`]+)`')
    AUTODOC = re.compile(
            r'\.\.\s+auto(?:function|class|method|attribute|data|exception)::'
            r'\s+([\w.:]+)')

    # Bare class names the docs use as shorthand, and where they live.
    SHORTHAND = {
        'Client': 'schwab.client',
        'AsyncClient': 'schwab.client',
        'StreamClient': 'schwab.streaming',
        'OrderBuilder': 'schwab.orders.generic',
    }

    @staticmethod
    def doc_files():
        found = [os.path.join(REPO_ROOT, 'docs', n)
                 for n in sorted(os.listdir(os.path.join(REPO_ROOT, 'docs')))
                 if n.endswith('.rst')]
        found.append(os.path.join(REPO_ROOT, 'README.rst'))
        return found

    @classmethod
    def references_in(cls, files):
        """Returns {dotted name: {'file:line', ...}} for every code reference."""
        refs = {}
        for path in files:
            with open(path, encoding='utf-8') as f:
                contents = f.read()
            for pattern, take_target in ((cls.ROLE, True),
                                         (cls.AUTODOC, False)):
                for m in pattern.finditer(contents):
                    body = m.group(1)
                    if take_target:
                        inner = re.search(r'<([^>]+)>', body)
                        body = inner.group(1) if inner else body
                    name = body.strip().lstrip('~').replace('()', '')
                    name = name.replace('::', '.')
                    line = contents[:m.start()].count('\n') + 1
                    refs.setdefault(name, set()).add(
                            '%s:%d' % (os.path.basename(path), line))
        return refs

    @classmethod
    def unresolvable(cls, refs):
        broken = []
        for name, where in sorted(refs.items()):
            parts = name.split('.')
            if parts[0] in cls.SHORTHAND:
                obj = importlib.import_module(cls.SHORTHAND[parts[0]])
                rest = parts
            elif parts[0] == 'schwab':
                obj, rest = None, None
                for i in range(len(parts), 0, -1):
                    try:
                        obj = importlib.import_module('.'.join(parts[:i]))
                    except ImportError:
                        continue
                    rest = parts[i:]
                    break
                if obj is None:
                    broken.append((name, sorted(where)))
                    continue
            else:
                # Not one of ours -- a python.org type, or prose in a role.
                continue
            for attr in rest:
                if not hasattr(obj, attr):
                    broken.append((name, sorted(where)))
                    break
                obj = getattr(obj, attr)
        return broken

    @no_duplicates
    def test_every_documented_name_resolves(self):
        files = self.doc_files()

        # Positive control for the collection, twice over: an empty file list
        # and a pattern that matches nothing both produce an empty broken list.
        self.assertGreater(len(files), 8)
        refs = self.references_in(files)
        self.assertGreater(len(refs), 150)
        self.assertIn('schwab.client.Client.get_quote', refs)

        broken = self.unresolvable(refs)
        self.assertEqual([], broken)

    @no_duplicates
    def test_the_check_reads_the_target_not_the_label(self):
        # The form that hid `search_instruments`: the visible label is not the
        # target, and a checker reading the label skips it as foreign.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'doc.rst')
            with open(path, 'w') as f:
                f.write(
                    'Use :meth:`Client.search_instruments() '
                    '<schwab.client.Client.search_instruments>` for this.\n'
                    'And :meth:`schwab.client.Client.get_quote` for that.\n'
                    '.. autoclass:: schwab.streaming::StreamClient.NoSuchEnum\n')

            refs = self.references_in([path])
            broken = self.unresolvable(refs)

        self.assertEqual(
                ['schwab.client.Client.search_instruments',
                 'schwab.streaming.StreamClient.NoSuchEnum'],
                sorted(name for name, _ in broken))


class DocExampleTest(unittest.TestCase):
    """Keyword arguments in documentation examples, against real signatures.

    `client.rst` showed placing an order with
    `easy_client(..., webdriver_func=make_webdriver)` and a selenium import.
    There is no `webdriver_func` parameter and selenium is not a dependency and
    appears nowhere in the library -- it is left over from the TD Ameritrade
    era, when the login flow drove a real browser. A reader following that
    example got a TypeError before reaching the part they came for.

    `DocReferenceTest` cannot see this: the reference role `:func:`easy_client``
    resolves perfectly well. What is wrong is the call written underneath it.
    This walks the python code blocks instead and checks that every keyword
    passed to a `schwab` callable is one that callable accepts.

    Deliberately narrow. It resolves a call only when the name is one the
    documentation imported from `schwab`, and it skips a callable that takes
    `**kwargs`. It is not a type checker; it catches the argument that used to
    exist and does not any more, which is the one that rots.
    """

    CODE_BLOCK = re.compile(
            r'\.\.\s+code-block::\s*python\s*\n\n((?:(?:[ \t]+[^\n]*)?\n)+)')

    @staticmethod
    def dedent(block):
        lines = block.split('\n')
        indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
        if not indents:
            return ''
        margin = min(indents)
        return '\n'.join(l[margin:] if l.strip() else '' for l in lines)

    @classmethod
    def code_blocks_in(cls, files):
        blocks = []
        for path in files:
            with open(path, encoding='utf-8') as f:
                contents = f.read()
            for m in cls.CODE_BLOCK.finditer(contents):
                line = contents[:m.start()].count('\n') + 1
                blocks.append((os.path.basename(path), line,
                               cls.dedent(m.group(1))))
        return blocks

    @staticmethod
    def resolve_callable(name, imported):
        """Resolve a called name to a schwab callable, or None if not ours."""
        root = name.split('.')[0]
        if root not in imported:
            return None
        obj = imported[root]
        for attr in name.split('.')[1:]:
            obj = getattr(obj, attr, None)
            if obj is None:
                return None
        return obj if callable(obj) else None

    @classmethod
    def bad_keywords_in(cls, blocks):
        """Returns (where, call, keyword) for each keyword the callee rejects."""
        problems = []
        for where, line, code in blocks:
            try:
                tree = ast.parse(code)
            except SyntaxError:
                # Fragments and shell-ish snippets are not our business.
                continue

            imported = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and \
                        (node.module or '').startswith('schwab'):
                    for alias in node.names:
                        try:
                            mod = importlib.import_module(node.module)
                        except ImportError:                # pragma: no cover
                            continue
                        target = getattr(mod, alias.name, None)
                        if target is not None:
                            imported[alias.asname or alias.name] = target
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('schwab'):
                            try:
                                imported[alias.asname or alias.name] = \
                                        importlib.import_module(alias.name)
                            except ImportError:            # pragma: no cover
                                pass

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                try:
                    name = ast.unparse(node.func)
                except Exception:                          # pragma: no cover
                    continue
                target = cls.resolve_callable(name, imported)
                if target is None:
                    continue
                try:
                    sig = inspect.signature(target)
                except (ValueError, TypeError):             # pragma: no cover
                    continue
                if any(p.kind is inspect.Parameter.VAR_KEYWORD
                       for p in sig.parameters.values()):
                    continue
                accepted = set(sig.parameters)
                for kw in node.keywords:
                    if kw.arg is not None and kw.arg not in accepted:
                        problems.append(
                                ('%s:%d' % (where, line), name, kw.arg))
        return sorted(set(problems))

    @no_duplicates
    def test_no_example_passes_an_argument_that_does_not_exist(self):
        blocks = DocReferenceTest.doc_files()
        blocks = self.code_blocks_in(blocks)

        # Positive control for the collection: an empty block list makes the
        # assertion below hold for the wrong reason. Also prove a real call is
        # being resolved and checked, not merely parsed.
        self.assertGreater(len(blocks), 20)
        resolved = sum(
                1 for _, _, code in blocks
                if 'easy_client(' in code or 'client_from_login_flow(' in code)
        self.assertGreater(resolved, 1)

        self.assertEqual([], self.bad_keywords_in(blocks))

    @no_duplicates
    def test_the_check_catches_the_argument_that_was_removed(self):
        # webdriver_func, verbatim from the example this was written for.
        code = ('from schwab.auth import easy_client\n'
                'c = easy_client(\n'
                "        token_path='/path/to/token.json',\n"
                "        api_key='api-key',\n"
                "        app_secret='app-secret',\n"
                "        callback_url='https://callback.example.com',\n"
                '        webdriver_func=make_webdriver)\n')
        problems = self.bad_keywords_in([('doc.rst', 1, code)])
        self.assertEqual([('doc.rst:1', 'easy_client', 'webdriver_func')],
                         problems)

    @no_duplicates
    def test_a_correct_call_is_not_flagged(self):
        # The same call, as it is actually written now. Without this the test
        # above passes for a checker that flags everything.
        code = ('from schwab.auth import easy_client\n'
                'c = easy_client(\n'
                "        api_key='api-key',\n"
                "        app_secret='app-secret',\n"
                "        callback_url='https://127.0.0.1:8182',\n"
                "        token_path='/path/to/token.json')\n")
        self.assertEqual([], self.bad_keywords_in([('doc.rst', 1, code)]))
