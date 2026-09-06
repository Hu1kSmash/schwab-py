import warnings as _warnings


def _installed_distribution_names():
    """Returns the normalised names of the distributions on `sys.path`.

    A directory scan rather than `importlib.metadata.distributions()`, which
    has to read and parse metadata for every installed package. Measured here
    against 93 installed packages: 0.2 ms for the scan against 48 ms for the
    metadata lookup, on an `import schwab` that is otherwise around 150 ms.
    Both agree in both states, so the lookup would add a third to import time
    and tell us nothing extra -- the wrong trade in a library that gets
    imported on a latency path.

    Only `.dist-info` counts. That is what pip writes for both of these
    distributions, and has been for every install method since PEP 660 --
    including editable ones. `.egg-info` is what a *source tree* accumulates
    as a build artefact, and a checkout of this repository on `sys.path` (any
    `pytest` run from the root) carries one; counting those made the check
    report a collision against the project's own working tree.

    Best effort by construction, and a miss costs a warning rather than
    correctness -- the documentation covers the same ground.

    Names come back normalised per PEP 503 -- lowercased with runs of `-`,
    `_` and `.` collapsed to a single `-` -- so `schwab_py` and `schwab-py`
    are the one name.
    """
    import os as _os
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
            # The version is the boundary, not the first hyphen: a name can
            # contain one (`schwab-py-2.5.1.dist-info`, which older tooling
            # wrote before the escaped spelling became the rule), and
            # splitting on the first would read that as a project called
            # `schwab`. A version component always begins with a digit.
            head, sep, tail = stem.rpartition('-')
            project = head if (sep and tail[:1].isdigit()) else stem
            normalised = ''
            for char in project:
                normalised += '-' if char in '-_.' else char
            while '--' in normalised:
                normalised = normalised.replace('--', '-')
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
