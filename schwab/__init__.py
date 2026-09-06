import warnings as _warnings


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

    Only `.dist-info` counts, and the reason is that `.egg-info` is
    ambiguous rather than merely old: the same name is written both into
    `site-packages` by a legacy install and into a *source tree* as a build
    artefact, and nothing about the name separates them. A checkout is on
    `sys.path` for every `pytest` run from its root and carries one, so
    counting them means reporting a project as installed because its source
    is present. `.dist-info` has no such ambiguity, and it is what pip writes
    for both of these distributions under every install method since PEP 660,
    editable included.

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
        for name in listing:
            # Lowercased before matching: a case-insensitive filesystem can
            # hand back a spelling that never appeared in a package name.
            lowered = name.lower()
            if not lowered.endswith('.dist-info'):
                continue
            stem = lowered[:-len('.dist-info')]

            # `<name>-<version>`, or a bare `<name>`. Splitting at the last
            # hyphen is not enough on its own, because the name may itself
            # end in one: `schwab-py.dist-info` would give up its `py`. A
            # version component always begins with a digit, and a name never
            # does -- PEP 508 requires a letter or digit at both ends and pip
            # would resolve a leading-digit name as a version -- so that is
            # what separates the two readings.
            head, sep, tail = stem.rpartition('-')
            project = head if (sep and tail[:1].isdigit()) else stem

            normalised = _re.sub(r'[-_.]+', '-', project)
            if normalised:
                names.add(normalised)
    return names


def _schwab_py_is_also_installed():
    """Reports whether `schwaby` and `schwab-py` are both installed.

    Both must be registered for this to be a collision. Seeing `schwab-py`
    alone is this same project under the name it published before 2.6.0 --
    an editable install made from a checkout of that era still registers it,
    and warning there would fire on every developer's own working tree.
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

    One caveat, and it is deliberate: under `PYTHONWARNINGS=error` or
    `-W error` this *does* fail the import, because there a warning is an
    exception. That is the operator's own instruction -- they configured the
    process to treat any warning as fatal -- and quietly exempting this one
    would mean the configuration that asked to be told loudest is the only one
    told nothing. `-W error::UserWarning` or an explicit `ignore` filter for
    `RuntimeWarning` narrows it back if that is not wanted.
    """
    try:
        detected = _schwab_py_is_also_installed()
    except Exception:                                    # pragma: no cover
        # Never let a diagnostic break the import it is diagnosing.
        return

    if not detected:
        return

    # Deliberately outside the `except Exception` above. Under
    # `PYTHONWARNINGS=error` a warning *is* an exception, and swallowing it
    # there would turn the one configuration that asked to be told loudly
    # into the one configuration that hears nothing.
    _warnings.warn(
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
        'modules removed in this one may still be importable.',
        RuntimeWarning, stacklevel=2)


_warn_if_schwab_py_is_also_installed()

from . import auth
from . import client
from . import debug
from . import orders
from . import streaming
from . import utils

from .version import version as __version__

LOG_REDACTOR = debug.LogRedactor()
