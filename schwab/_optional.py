'''Imports for packages which only one entry point needs.

These are declared as extras in ``setup.py`` rather than hard dependencies
because the common case -- a long-running process which loads a token from a
file and streams -- never touches them, and a bare install should not pull a
web framework onto a machine that places trades.

Lives in its own module rather than in ``auth``, which is where it started:
``contrib.orders`` and the code generator need it too, and importing ``auth``
to reach it drags in ``authlib`` and ``httpx2`` for the sake of a six-line
helper.
'''

import importlib


def import_optional(module_name, extra, needed_for):
    '''Imports ``module_name``, or raises an ImportError which explains itself.

    The failure has to name the extra: an ImportError for "flask" tells a
    caller nothing about what to install.
    '''
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        # Only a genuinely absent module gets the friendly message. A package
        # which is installed but raises ImportError while importing itself --
        # an incompatible werkzeug under flask, a half-removed distribution --
        # would otherwise be reported as missing, and the caller would be told
        # to install something they already have. Let that one through as
        # itself, which at least names the module that actually failed.
        #
        # Compared exactly, not by top-level package. A truncated install can
        # raise ModuleNotFoundError for 'flask.json', and treating that as
        # 'flask' being absent is the same misdirection one level down: the
        # extra is installed, so installing it again fixes nothing.
        if (not isinstance(exc, ModuleNotFoundError)
                or getattr(exc, 'name', None) != module_name):
            raise

        raise ImportError(
                '{} requires the {!r} extra, which is not installed. Install '
                'it with:\n\n'
                '    pip install "schwab-py[{}] @ '
                'git+https://github.com/Hu1kSmash/schwab-py@v{}"\n\n'
                '(missing module: {})'.format(
                    needed_for, extra, extra, _version(), module_name)) from exc


def _version():
    # Imported lazily: schwab.version is cheap, but this module is imported by
    # auth at module scope and there is no reason to widen that at import time.
    from schwab.version import version
    return version
