import warnings as _warnings


# `<name>`, `<name>-<version>`, or the legacy `setup.py install` spelling
# `<name>-<version>-py<X.Y>`. Splitting on a hyphen alone cannot do this: the
# name may contain one (`schwab-py-2.5.1`) and may also end in one
# (`schwab-py`, unversioned). A version component always begins with a digit
# and a name never does -- PEP 508 requires a letter or digit at each end, and
# a leading-digit name would resolve as a version -- so the digit is what
# separates the readings.
#
# The lazy `.+?` asks for the shortest name that still leaves a valid version.
# It makes no difference to any name a packaging tool writes -- a version
# component holds no hyphen, so a stem has at most one split point that can
# begin one, and greedy finds the same one; a mutation to `.+` is GREEN and
# `redproof.py` records it as such. It is kept because it is the correct
# general form, not because anything here depends on it.
_DIST_STEM = r'^(?P<name>.+?)-\d[^-]*(?:-py\d[\d.]*)?$'


def _installed_distribution_names():
    """Returns the normalised names of the distributions on `sys.path`.

    A directory listing rather than `importlib.metadata.distributions()`,
    which opens and parses a metadata file for every installed package. Both
    answer this question identically; the listing costs a fraction of a
    millisecond and the metadata walk costs tens of them, which on this
    machine is a sizeable fraction of `import schwab` itself. Numbers are not
    quoted here because they move with the machine, the filesystem cache and
    the number of packages installed -- `CHANGELOG.md` records what was
    measured and how. Paying any of it for a diagnostic is the wrong trade in
    a library that gets imported on a latency path.

    Both `.dist-info` and `.egg-info` count. `.egg-info` cannot simply be
    skipped: on a Debian or Ubuntu system interpreter the distro-packaged
    modules register that way and nothing else does --- measured here at 73
    `.egg-info` against 35 `.dist-info`, so ignoring the layout would hide
    two thirds of what is installed and make this function's name a lie.

    What it does need is a discriminator, because setuptools writes the same
    spelling into a *source tree* as a build artefact, and a checkout is on
    `sys.path` for every `pytest` run from its root. An install directory
    never contains `setup.py` or `pyproject.toml` and a source tree always
    does, so the parent directory settles it --- one `os.path.isfile` per
    `sys.path` entry, not per name.

    Best effort by construction, and a miss costs a warning rather than
    correctness -- the documentation covers the same ground.

    Names come back normalised per PEP 503 -- lowercased with runs of `-`,
    `_` and `.` collapsed to a single `-` -- so `schwab_py` and `schwab-py`
    are the one name.
    """
    import os as _os
    import re as _re
    import sys as _sys

    names = set()
    for entry in _sys.path:
        if not entry or not _os.path.isdir(entry):
            continue
        try:
            listing = _os.listdir(entry)
        except OSError:
            continue

        # A source tree's `.egg-info` says "this is the project you are
        # standing in", not "this project is installed".
        is_source_tree = any(
                marker in listing
                for marker in ('setup.py', 'pyproject.toml', 'setup.cfg'))

        for name in listing:
            # Lowercased before matching: a case-insensitive filesystem can
            # hand back a spelling that never appeared in a package name.
            lowered = name.lower()
            if lowered.endswith('.dist-info'):
                stem = lowered[:-len('.dist-info')]
            elif lowered.endswith('.egg-info') and not is_source_tree:
                stem = lowered[:-len('.egg-info')]
            else:
                continue

            match = _re.match(_DIST_STEM, stem)
            project = match.group('name') if match else stem

            normalised = _re.sub(r'[-_.]+', '-', project)
            if normalised:
                names.add(normalised)
    return names


def _editable_source_directories():
    """Returns the source directories of the two names' editable installs.

    A `dict` of normalised distribution name -> set of directories, built from
    the `direct_url.json` pip writes beside an install it made from a local
    path. Only the two names this module cares about are looked up, and only
    when a collision has already been detected, so this reads at most a
    handful of small files and never runs on a clean install.
    """
    import json as _json
    import os as _os
    import re as _re
    import sys as _sys

    found = {}
    for entry in _sys.path:
        if not entry or not _os.path.isdir(entry):
            continue
        try:
            listing = _os.listdir(entry)
        except OSError:
            continue
        for name in listing:
            lowered = name.lower()
            if not lowered.endswith('.dist-info'):
                continue
            match = _re.match(_DIST_STEM, lowered[:-len('.dist-info')])
            project = match.group('name') if match else lowered[:-10]
            project = _re.sub(r'[-_.]+', '-', project)
            if project not in ('schwaby', 'schwab-py'):
                continue
            try:
                with open(_os.path.join(entry, name, 'direct_url.json'),
                          encoding='utf-8') as f:
                    info = _json.load(f)
            except (OSError, ValueError):
                # No `direct_url.json` at all is the ordinary case: pip writes
                # one only for an install made from a URL or a local path, so
                # anything from PyPI has none. Treated as "not editable",
                # which is what it is.
                found.setdefault(project, set()).add(None)
                continue
            url = info.get('url')
            editable = (info.get('dir_info') or {}).get('editable')
            found.setdefault(project, set()).add(url if editable else None)
    return found


def _is_one_working_tree_registered_twice():
    """Reports whether the two names are one checkout registered under both.

    pip uninstalls by project name, so a virtualenv that carried a pre-2.6.0
    editable install and then received `pip install -e .` at 3.x holds two
    registrations --- `schwab_py` and `schwaby` --- whose editable finders
    both resolve to the *same single* source tree. Nothing is duplicated and
    nothing is at risk, so warning is wrong.

    It is worse than wrong. The remedy the warning prints,
    `pip uninstall -y schwab-py schwaby && pip install schwaby`, would in
    that state delete the developer's editable registration and replace their
    checkout with the PyPI release.

    `direct_url.json` settles it: two editable installs naming the same
    directory are one tree, and anything else --- a missing file, a
    non-editable install, two different directories --- is not.
    """
    directories = _editable_source_directories()
    urls = directories.get('schwaby', set()) | directories.get(
            'schwab-py', set())
    return len(urls) == 1 and None not in urls


def _schwab_py_is_also_installed():
    """Reports whether `schwaby` and `schwab-py` are both really installed.

    Both must be registered for this to be a collision. Seeing `schwab-py`
    alone is this same project under the name it published before 2.6.0 --
    an editable install made from a checkout of that era still registers it,
    and warning there would fire on every developer's own working tree.

    Both being registered is still not sufficient, because they may be the
    same working tree registered twice; see
    `_is_one_working_tree_registered_twice`, which only runs once the names
    say there is something to check.
    """
    installed = _installed_distribution_names()
    if not ('schwaby' in installed and 'schwab-py' in installed):
        return False
    return not _is_one_working_tree_registered_twice()


def _warn_if_schwab_py_is_also_installed():
    """Warns when the `schwab-py` distribution is installed alongside this one.

    `schwaby` and `schwab-py` both provide the `schwab` package, and `pip` has
    no idea they are the same project, so installing one over the other leaves
    both registered and both claiming the same files. What follows is worse
    than the overlap:

    * modules deleted in the newer version survive on disk and stay importable,
      so you can import something the version you installed does not have;
    * `pip uninstall schwab-py`, the obvious next step, removes the shared
      files and destroys the install. `pip` goes on reporting `schwaby` as
      present while `import schwab` raises `ModuleNotFoundError`.

    `pip` says nothing at any point -- it does not implement `Conflicts-Dist`;
    its resolver never reads the field. And a wheel runs no code when it is
    installed, by design. So import is the first moment this can be said at
    all, which is why it is said here rather than somewhere more sensible.

    A warning rather than an exception on purpose. This library places orders,
    and a hard failure at import in a running system is worse than the state it
    would be complaining about -- the installed files usually work; it is the
    next `pip uninstall` that does the damage. The person who needs to act is a
    human reading output, so give them something to read.

    Under `PYTHONWARNINGS=error`, `-W error`, or a consumer's pytest
    `filterwarnings = error`, a warning *is* an exception, and those two
    requirements collide: raising would fail the import for a condition where
    the files on disk still work, and swallowing would leave the one
    configuration that asked to be told loudest as the only one told nothing.
    So the `warn()` is caught and the same text printed to stderr instead.
    The operator is told either way, and `import schwab` does not die of a
    diagnostic.
    """
    try:
        detected = _schwab_py_is_also_installed()
    except Exception:                                    # pragma: no cover
        # Never let a diagnostic break the import it is diagnosing.
        return

    if not detected:
        return

    message = (
        'Both `schwaby` and `schwab-py` are installed. They provide the '
        'same `schwab` package and pip does not know they are the same '
        'project, so they are now claiming the same files.\n'
        '\n'
        'Do NOT run `pip uninstall schwab-py` from here: it deletes the '
        'shared files and leaves an install that pip reports as present '
        'and that cannot be imported.\n'
        '\n'
        'Fix it by removing both and reinstalling:\n'
        '    pip uninstall -y schwab-py schwaby && pip install schwaby\n'
        '\n'
        'Until then you may be running code from either version, and '
        'modules removed in this one may still be importable.')

    # Deliberately outside the `except Exception` above, and deliberately
    # narrow. `except Warning` catches only the warnings-as-errors case --
    # anything else still propagates -- and the fallback means that case is
    # told rather than silenced. Catching it here is what keeps the promise
    # three paragraphs up: no diagnostic fails this import.
    try:
        _warnings.warn(message, RuntimeWarning, stacklevel=2)
    except Warning:
        import sys as _sys
        print('RuntimeWarning: ' + message, file=_sys.stderr)


_warn_if_schwab_py_is_also_installed()

from . import auth
from . import client
from . import debug
from . import orders
from . import streaming
from . import utils

from .version import version as __version__

LOG_REDACTOR = debug.LogRedactor()
