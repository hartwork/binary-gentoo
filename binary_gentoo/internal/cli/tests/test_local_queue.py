# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from dataclasses import dataclass
from io import StringIO
from tempfile import NamedTemporaryFile
from textwrap import dedent
from unittest import TestCase
from unittest.mock import patch

from ..local_queue import main


@dataclass
class RunRecord:
    stdout: str
    stderr: str
    exit_code: int


class MainTest(TestCase):
    def setUp(self) -> None:
        self._state_file = NamedTemporaryFile().__enter__()

    def tearDown(self) -> None:
        self._state_file.__exit__(None, None, None)

    def _run_gentoo_local_queue(self, *argv_extra):
        argv = ['gentoo-local-queue', '--state', self._state_file.name] + list(argv_extra)
        exit_code = 0

        with patch('sys.argv', argv), \
                patch('sys.stdout', StringIO()) as stdout_mock, \
                patch('sys.stderr', StringIO()) as stderr_mock:
            try:
                main()
            except SystemExit as e:
                exit_code = e.code

        return RunRecord(
            stdout=stdout_mock.getvalue(),
            stderr=stderr_mock.getvalue(),
            exit_code=exit_code,
        )

    def test_push(self):
        run_record = self._run_gentoo_local_queue('push', '1.0', 'cat/pkg-one')

        self.assertEqual(run_record.exit_code, 0)
        self.assertEqual(run_record.stdout, '')
        self.assertEqual(run_record.stderr, '')

    def test_drop__existing(self):
        self._run_gentoo_local_queue('push', '1.0', 'cat/pkg-one')

        run_record = self._run_gentoo_local_queue('drop', 'cat/pkg-one')

        self.assertEqual(run_record.exit_code, 0)
        self.assertEqual(run_record.stdout, '')
        self.assertEqual(run_record.stderr, '')

    def test_drop__non_existing(self):
        run_record = self._run_gentoo_local_queue('drop', 'cat/pkg-one')

        self.assertEqual(run_record.exit_code, 1)
        self.assertEqual(run_record.stdout, '')
        self.assertEqual(
            run_record.stderr,
            dedent("""\
                ERROR: Atom 'cat/pkg-one' not currently in the queue
        """))

    def test_pop__empty(self):
        run_record = self._run_gentoo_local_queue('pop')

        self.assertEqual(run_record.exit_code, 1)
        self.assertEqual(run_record.stdout, '')
        self.assertEqual(run_record.stderr,
                         dedent("""\
            ERROR: Queue is empty
        """))

    def test_pop__not_empty(self):
        self._run_gentoo_local_queue('push', '2.0', 'cat/pkg-two')
        self._run_gentoo_local_queue('push', '1.0', 'cat/pkg-one')
        self._run_gentoo_local_queue('push', '3.0', 'cat/pkg-three')

        run_record = self._run_gentoo_local_queue('pop')

        self.assertEqual(run_record.exit_code, 0)
        self.assertEqual(
            run_record.stdout,
            dedent("""\
                {
                  "atom": "cat/pkg-one",
                  "priority": 1.0,
                  "version": 2
                }
            """))
        self.assertEqual(run_record.stderr, '')

    def test_show__empty(self):
        run_record = self._run_gentoo_local_queue('show')

        self.assertEqual(run_record.exit_code, 0)
        self.assertEqual(run_record.stdout, '')
        self.assertEqual(run_record.stderr, '')

    def test_show__not_empty(self):
        self._run_gentoo_local_queue('push', '2.0', 'cat/pkg-two')
        self._run_gentoo_local_queue('push', '1.0', 'cat/pkg-one')
        self._run_gentoo_local_queue('push', '3.0', 'cat/pkg-three')

        run_record = self._run_gentoo_local_queue('show')

        self.assertEqual(run_record.exit_code, 0)
        self.assertEqual(
            run_record.stdout,
            dedent("""\
                1.0 cat/pkg-one
                2.0 cat/pkg-two
                3.0 cat/pkg-three
            """))
        self.assertEqual(run_record.stderr, '')
