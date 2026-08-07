import atexit
import io
import json
import logging
import schwab
import unittest

from schwab.client import Client
from .utils import MockResponse, no_duplicates
from unittest.mock import Mock, patch


class RedactorTest(unittest.TestCase):

    def setUp(self):
        self.redactor = schwab.debug.LogRedactor()

    @no_duplicates
    def test_no_redactions(self):
        self.assertEqual('test message', self.redactor.redact('test message'))

    @no_duplicates
    def test_simple_redaction(self):
        self.redactor.register('secret', 'SECRET')

        self.assertEqual(
            '<REDACTED SECRET> message',
            self.redactor.redact('secret message'))

    @no_duplicates
    def test_multiple_registrations_same_string(self):
        self.redactor.register('secret', 'SECRET')
        self.redactor.register('secret', 'SECRET')

        self.assertEqual(
            '<REDACTED SECRET> message',
            self.redactor.redact('secret message'))

    @no_duplicates
    def test_multiple_registrations_same_string_different_label(self):
        self.redactor.register('secret-A', 'SECRET')
        self.redactor.register('secret-B', 'SECRET')

        self.assertEqual(
            '<REDACTED SECRET-1> message <REDACTED SECRET-2>',
            self.redactor.redact('secret-A message secret-B'))


class RegisterRedactionsTest(unittest.TestCase):

    def setUp(self):
        self.captured = io.StringIO()
        self.logger = logging.getLogger('test')
        self.dump_logs = schwab.debug._enable_bug_report_logging(
            output=self.captured, loggers=[self.logger])
        schwab.LOG_REDACTOR = schwab.debug.LogRedactor()

    @no_duplicates
    def test_empty_string(self):
        schwab.debug.register_redactions('')

    @no_duplicates
    def test_empty_dict(self):
        schwab.debug.register_redactions({})

    @no_duplicates
    def test_empty_list(self):
        schwab.debug.register_redactions([])

    @no_duplicates
    def test_dict(self):
        schwab.debug.register_redactions(
            {'BadNumber': '100001'},
            bad_patterns=['bad'])
        schwab.debug.register_redactions(
            {'OtherBadNumber': '200002'},
            bad_patterns=['bad'])

        self.logger.info('Bad Number: 100001')
        self.logger.info('Other Bad Number: 200002')

        self.dump_logs()
        self.assertRegex(
            self.captured.getvalue(),
            r'\[.*\] Bad Number: <REDACTED BadNumber>\n' +
            r'\[.*\] Other Bad Number: <REDACTED OtherBadNumber>\n')

    @no_duplicates
    def test_list_of_dict(self):
        schwab.debug.register_redactions(
            [{'GoodNumber': '900009'},
             {'BadNumber': '100001'},
             {'OtherBadNumber': '200002'}],
            bad_patterns=['bad'])

        self.logger.info('Good Number: 900009')
        self.logger.info('Bad Number: 100001')
        self.logger.info('Other Bad Number: 200002')

        self.dump_logs()
        self.assertRegex(
            self.captured.getvalue(),
            r'\[.*\] Good Number: 900009\n' +
            r'\[.*\] Bad Number: <REDACTED 1-BadNumber>\n' +
            r'\[.*\] Other Bad Number: <REDACTED 2-OtherBadNumber>\n')

    @no_duplicates
    def test_whitelist(self):
        schwab.debug.register_redactions(
            [{'GoodNumber': '900009'},
             {'BadNumber': '100001'},
             {'OtherBadNumber': '200002'}],
            bad_patterns=['bad'],
            whitelisted=['otherbadnumber'])

        self.logger.info('Good Number: 900009')
        self.logger.info('Bad Number: 100001')
        self.logger.info('Other Bad Number: 200002')

        self.dump_logs()
        self.assertRegex(
            self.captured.getvalue(),
            r'\[.*\] Good Number: 900009\n' +
            r'\[.*\] Bad Number: <REDACTED 1-BadNumber>\n' +
            r'\[.*\] Other Bad Number: 200002\n')

    @no_duplicates
    @patch('schwab.debug.register_redactions', new_callable=Mock)
    def test_register_from_request_success(self, register_redactions):
        resp = MockResponse({'success': 1}, 200)
        schwab.debug.register_redactions_from_response(resp)
        register_redactions.assert_called_with({'success': 1})

    @no_duplicates
    @patch('schwab.debug.register_redactions', new_callable=Mock)
    def test_register_from_request_not_okay(self, register_redactions):
        resp = MockResponse({'success': 1}, 403)
        schwab.debug.register_redactions_from_response(resp)
        register_redactions.assert_not_called()

    @no_duplicates
    @patch('schwab.debug.register_redactions', new_callable=Mock)
    def test_register_unparseable_json(self, register_redactions):
        class MR(MockResponse):
            def json(self):
                raise json.decoder.JSONDecodeError('e243rschwabgew', '', 0)

        resp = MR({'success': 1}, 200)
        schwab.debug.register_redactions_from_response(resp)
        register_redactions.assert_not_called()

class EnableDebugLoggingTest(unittest.TestCase):

    @patch('atexit.register')
    @patch('logging.Logger.addHandler')
    def test_enable_doesnt_throw_exceptions(self, _, __):
        try:
            schwab.debug.enable_bug_report_logging()
        except AttributeError:
            self.fail("debug.enable_bug_report_logging() raised AttributeError unexpectedly")

    @no_duplicates
    def test_writes_to_stderr_as_it_is_at_exit(self):
        # The logs are written at program exit, so the stream to write them to
        # is whatever sys.stderr is then -- not whatever it happened to be when
        # this module was imported.
        replacement = io.StringIO()
        dump_logs = schwab.debug._enable_bug_report_logging(
                loggers=[logging.getLogger('test-late-binding')])
        self.addCleanup(atexit.unregister, dump_logs)
        logging.getLogger('test-late-binding').info('a line worth reporting')

        with patch('sys.stderr', replacement):
            dump_logs()

        self.assertIn('a line worth reporting', replacement.getvalue())

    @no_duplicates
    def test_does_not_write_to_a_stream_whose_reader_has_gone(self):
        # `python bot.py 2>&1 | head -20` is enough: head exits, the pipe
        # breaks, and at interpreter shutdown this handler would produce
        # exactly the traceback it exists to avoid. BrokenPipeError is an
        # OSError, not a ValueError.
        class BrokenPipe(io.StringIO):
            def write(self, s):
                raise BrokenPipeError(32, 'Broken pipe')

        dump_logs = schwab.debug._enable_bug_report_logging(
                output=BrokenPipe(),
                loggers=[logging.getLogger('test-broken-pipe')])
        self.addCleanup(atexit.unregister, dump_logs)

        dump_logs()

    @no_duplicates
    def test_does_not_write_to_a_stream_closed_before_exit(self):
        # An application which replaced sys.stderr and then closed it should
        # not have a traceback out of an atexit handler as its last output.
        closed = io.StringIO()
        dump_logs = schwab.debug._enable_bug_report_logging(
                loggers=[logging.getLogger('test-closed-stream')])
        self.addCleanup(atexit.unregister, dump_logs)
        closed.close()

        with patch('sys.stderr', closed):
            dump_logs()
