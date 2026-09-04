'''Tests for bin/schwab-generate-token.py.

It is a script rather than a module, so it is loaded by path. Thin as it is,
it is the one login entry point a plain install still puts on PATH, and it used
to catch everything -- including the ImportError which says the 'login' extra
is missing, and including Ctrl-C.
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
    def test_a_missing_extra_is_named_and_the_manual_flow_still_runs(
            self, login_flow, manual_flow):
        login_flow.side_effect = ImportError(
                "The interactive login flow requires the 'login' extra, which "
                "is not installed.")

        with patch('builtins.print') as mock_print:
            self.assertEqual(0, self.main())

        # The message the user needs is the one that reaches them. Reported as
        # a generic browser failure, they would take the manual flow on every
        # run without ever learning why.
        printed = ' '.join(str(c) for c in mock_print.call_args_list)
        self.assertIn("'login' extra", printed)

        # And they still get a token: the manual flow needs no optional
        # package, so refusing here would withhold the one thing that works.
        manual_flow.assert_called_once()

    @no_duplicates
    @patch('schwab.auth.client_from_manual_flow')
    @patch('schwab.auth.client_from_login_flow')
    def test_a_broken_package_is_named_and_the_manual_flow_still_runs(
            self, login_flow, manual_flow):
        # import_optional re-raises unchanged when a package is installed but
        # fails to import itself. That is an ImportError too, and it is no more
        # a reason to refuse the manual flow than a missing package is.
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
