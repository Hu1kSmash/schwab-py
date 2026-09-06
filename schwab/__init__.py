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


def _distribution_records():
    """Yields `(normalised name, metadata directory)` for what is installed.

    The single walk of `sys.path`. It stays a separate function from its one
    caller because it briefly had two, which each decided for themselves which
    layouts to read; they disagreed about `.egg-info`, and the disagreement
    silently suppressed the warning this module exists to emit. Anything that
    needs to know what is installed asks here.

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
    `.egg-info` against 35 `.dist-info` --- so ignoring the layout would hide
    two thirds of what is installed and make this function's name a lie.

    The discriminator is the *directory*, not the layout. A checkout is on
    `sys.path` for every `pytest` run from its root, and it accumulates both
    spellings as build artefacts --- `.egg-info` from an editable install or
    an sdist build, `.dist-info` from `setup.py dist_info`. Either read as an
    install says "this project is installed here" on the strength of its
    source being present, which is the false positive this whole release
    exists to remove. An install directory never contains `setup.py` or
    `pyproject.toml` and a source tree always does, so the entry's own
    listing settles it --- no extra syscall, just a membership test against
    names already fetched.

    Best effort by construction, and a miss costs a warning rather than
    correctness -- the documentation covers the same ground.

    Names come back normalised per PEP 503 -- lowercased with runs of `-`,
    `_` and `.` collapsed to a single `-` -- so `schwab_py` and `schwab-py`
    are the one name.
    """
    import os as _os
    import re as _re
    import sys as _sys

    for entry in _sys.path:
        if not entry or not _os.path.isdir(entry):
            continue
        try:
            listing = _os.listdir(entry)
        except OSError:
            continue

        # A source tree's `.egg-info` says "this is the project you are
        # standing in", not "this project is installed".
        names = set(listing)
        is_source_tree = bool(
                names & {'setup.py', 'pyproject.toml', 'setup.cfg'})

        for name in listing:
            # Lowercased before matching: a case-insensitive filesystem can
            # hand back a spelling that never appeared in a package name.
            lowered = name.lower()
            if is_source_tree:
                # Both layouts, not just `.egg-info`: `setup.py dist_info`
                # writes a `.dist-info` into the checkout root, and reading
                # that as an install recreates the exact false positive this
                # release exists to remove -- the project colliding with
                # itself.
                continue
            if lowered.endswith('.dist-info'):
                stem = lowered[:-len('.dist-info')]
            elif lowered.endswith('.egg-info'):
                stem = lowered[:-len('.egg-info')]
            else:
                continue

            match = _re.match(_DIST_STEM, stem)
            project = match.group('name') if match else stem

            normalised = _re.sub(r'[-_.]+', '-', project)
            if normalised:
                yield normalised, _os.path.join(entry, name)


def _installed_distribution_names():
    """Returns the normalised names of the distributions on `sys.path`."""
    return {name for name, _ in _distribution_records()}


def _schwab_py_is_also_installed():
    """Reports whether `schwaby` and `schwab-py` are both installed.

    Both must be registered for this to be a collision. Seeing `schwab-py`
    alone is this same project under the name it published before 2.6.0 --
    an editable install made from a checkout of that era still registers it,
    and warning there would fire on every developer's own working tree.

    One case is deliberately not distinguished: a virtualenv that carried a
    pre-2.6.0 *editable* install and then received `pip install -e .` holds
    both names for one source tree, and this reports it. Telling that apart
    needs `direct_url.json` from both sides, which was written, reviewed, and
    removed --- it was a third of this check's code, produced the only two
    serious defects five review rounds found, and separated one arrangement
    from another for a reader who can fix it with `pip uninstall schwab-py`.
    The cost of the false positive is one wrong warning in a maintainer's
    own venv; the cost of the code was worse.
    """
    installed = _installed_distribution_names()
    return 'schwaby' in installed and 'schwab-py' in installed


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
    diagnostic -- unconditionally: a replaced `warnings.showwarning` that
    raises something other than a `Warning`, and a stderr that is closed by
    the time the fallback runs, are both absorbed too.
    """
    try:
        detected = _schwab_py_is_also_installed()
    except Exception:
        # Never let a diagnostic break the import it is diagnosing. Covered:
        # `test_a_broken_lookup_cannot_break_the_import` reaches it, and
        # `redproof.py` proves mutating it to `raise` turns that test red.
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

    # Deliberately outside the `except Exception` around the detection above:
    # swallowing there would leave warnings-as-errors the one configuration
    # told nothing.
    #
    # Two layers, because emission has two ways to fail and the promise three
    # paragraphs up is unconditional. `warn()` raises under `-W error`, and
    # can raise anything at all if `warnings.showwarning` has been replaced,
    # which daemonised and embedded hosts do. Then `print` can raise in turn
    # on a closed or detached stderr. A diagnostic that kills the import it is
    # diagnosing is the failure this whole function exists to avoid, so the
    # last resort is to give up quietly -- there is nowhere left to say it.
    try:
        _warnings.warn(message, RuntimeWarning, stacklevel=2)
    except Exception:
        try:
            import sys as _sys
            # `sys.stderr` is None under pythonw and in hosts that detach it
            # --- the same hosts that replace `showwarning`. `print(file=None)`
            # falls back to stdout, which would inject a multi-line diagnostic
            # into whatever the program emits as data.
            if _sys.stderr is not None:
                print('RuntimeWarning: ' + message, file=_sys.stderr)
        except Exception:                                # pragma: no cover
            pass


_warn_if_schwab_py_is_also_installed()

from . import auth
from . import client
from . import debug
from . import orders
from . import streaming
from . import utils

from .version import version as __version__

LOG_REDACTOR = debug.LogRedactor()
