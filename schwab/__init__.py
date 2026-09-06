import warnings as _warnings


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

    Nothing warns you at any point -- not `pip`, not the metadata. `pip` does
    not implement `Conflicts-Dist`; its resolver never reads the field. And a
    wheel runs no code when it is installed, by design. So import is the first
    moment this can be said at all, which is why it is said here rather than
    somewhere more sensible.

    A warning rather than an exception on purpose. This library places orders,
    and a hard failure at import in a running system is worse than the state it
    would be complaining about -- the installed files usually work; it is the
    next `pip uninstall` that does the damage. The person who needs to act is a
    human reading output, so give them something to read.
    """
    try:
        import os as _os
        import sys as _sys

        # A directory scan rather than importlib.metadata.distribution(),
        # which has to read and parse metadata for every installed package:
        # measured at 35 ms against 0.012 ms, on an import that is otherwise
        # about 190 ms. Both agree in both states. Paying 18% of import time
        # for a diagnostic is the wrong trade in a library that gets imported
        # on a latency path.
        #
        # Best effort by construction: it recognises the standard
        # `schwab_py-*.dist-info` and `.egg-info` layouts. A miss costs a
        # warning, not correctness, and the documentation covers the same
        # ground.
        found = False
        for _entry in _sys.path:
            if not _entry or not _os.path.isdir(_entry):
                continue
            try:
                _names = _os.listdir(_entry)
            except OSError:
                continue
            for _name in _names:
                _lower = _name.lower()
                if (_lower.startswith(('schwab_py-', 'schwab-py-'))
                        and _lower.endswith(('.dist-info', '.egg-info'))):
                    found = True
                    break
            if found:
                break

        if not found:
            return

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
    except Exception:                                    # pragma: no cover
        # Never let a diagnostic break the import it is diagnosing.
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
