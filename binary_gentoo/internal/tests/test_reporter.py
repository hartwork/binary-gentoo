# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import subprocess
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from ..reporter import (_readable_called_process_errors, _ReadableCalledProcessError,
                        exception_reporting)


class ReadableCalledProcessErrorsTest(TestCase):
    def test_called_process_error_is_made_more_readable(self):
        with self.assertRaises(_ReadableCalledProcessError) as catcher:
            with _readable_called_process_errors():
                subprocess.check_call(['false', 'one two  three   '])
        self.assertEqual(
            str(catcher.exception),
            '''Command "false 'one two  three   '" returned non-zero exit status 1.''')


class ExceptionReportingTest(TestCase):
    def test_keyboard_interrupt_exits_with_code_130(self):
        with self.assertRaises(SystemExit) as catcher:
            with exception_reporting():
                raise KeyboardInterrupt
        self.assertEqual(catcher.exception.code, 130)

    def test_exception_printed_to_stderr(self):
        with patch('sys.stderr', StringIO()) as stderr_mock:
            with self.assertRaises(SystemExit) as catcher:
                with exception_reporting():
                    raise ValueError('123')
        self.assertEqual(stderr_mock.getvalue(), 'ERROR: 123\n')
        self.assertEqual(catcher.exception.code, 1)
