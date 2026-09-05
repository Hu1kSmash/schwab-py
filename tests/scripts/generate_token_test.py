'''Tests for bin/schwab-generate-token.py.

It is a script rather than a module, so it is loaded by path. Thin as it is, it
is the one login entry point an install puts on PATH, and it used to catch
everything with a bare `except:` -- including Ctrl-C, which fell through into
the manual flow rather than quitting.
'''

import os
import unittest
from unittest.mock import patch

import importlib.util

from ..utils import no_duplicates


SCRIPT = os.path.join(
        os.path.dirname(__file__), '..', '..', 'bin',
        'schwab-generate-token.py')


def load_script():
    spec = importlib.util.spec_from_file_location('generate_token', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GenerateTokenTest(unittest.TestCase):

    def setUp(self):
        self.script = load_script()

    def main(self):
        return self.script.main(
                'api-key', 'app-secret', 'https://127.0.0.1:8182',
                '/tmp/token.json', None)

    @no_duplicates
    @patch('schwab.auth.client_from_manual_flow')
    @patch('schwab.auth.client_from_login_flow')
    def test_an_import_error_reaches_the_user_verbatim(
            self, login_flow, manual_flow):
        # This test used to fabricate the 'login' extra's ImportError and
        # assert that "'login' extra" reached the user. 3.0.0 deleted the code
        # that raised it and the test stayed green, because it was asserting on
        # a string it had invented itself. What is worth protecting is that
        # whatever the ImportError says reaches the user unchanged -- the
        # script cannot know what broke, so it must not summarise.
        login_flow.side_effect = ImportError(
                'cannot import name Markup from jinja2')

        with patch('builtins.print') as mock_print:
            self.assertEqual(0, self.main())

        # Reported as a generic browser failure, the user would take the manual
        # flow on every run without ever learning why.
        printed = ' '.join(str(c) for c in mock_print.call_args_list)
        self.assertIn('cannot import name Markup from jinja2', printed)

        # And they still get a token: the manual flow starts no callback server
        # and imports none of this, so refusing here would withhold the one
        # thing that still works.
        manual_flow.assert_called_once()

    @no_duplicates
    @patch('schwab.auth.client_from_manual_flow')
    @patch('schwab.auth.client_from_login_flow')
    def test_a_broken_package_is_named_and_the_manual_flow_still_runs(
            self, login_flow, manual_flow):
        # Since 3.0.0 flask, multiprocess and psutil are ordinary
        # dependencies, so a damaged environment rather than a missing one is
        # the usual cause -- a package installed but unable to import itself.
        # That is an ImportError too, and no more a reason to refuse.
        login_flow.side_effect = ModuleNotFoundError(
                "No module named 'werkzeug'", name='werkzeug')

        with patch('builtins.print') as mock_print:
            self.assertEqual(0, self.main())

        printed = ' '.join(str(c) for c in mock_print.call_args_list)
        self.assertIn('werkzeug', printed)
        manual_flow.assert_called_once()

    @no_duplicates
    @patch('schwab.auth.client_from_manual_flow')
    @patch('schwab.auth.client_from_login_flow')
    def test_an_ordinary_browser_failure_still_falls_back(
            self, login_flow, manual_flow):
        login_flow.side_effect = Exception('no browser here')

        with patch('builtins.print'):
            self.assertEqual(0, self.main())

        manual_flow.assert_called_once()

    @no_duplicates
    @patch('schwab.auth.client_from_manual_flow')
    @patch('schwab.auth.client_from_login_flow')
    def test_ctrl_c_quits_rather_than_starting_the_manual_flow(
            self, login_flow, manual_flow):
        login_flow.side_effect = KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            with patch('builtins.print'):
                self.main()

        manual_flow.assert_not_called()

    @no_duplicates
    @patch('schwab.auth.client_from_manual_flow')
    @patch('schwab.auth.client_from_login_flow')
    def test_success_does_not_reach_the_manual_flow(
            self, login_flow, manual_flow):
        self.assertEqual(0, self.main())
        manual_flow.assert_not_called()
