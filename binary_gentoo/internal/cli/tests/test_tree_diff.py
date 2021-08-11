# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os
from io import StringIO
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase
from unittest.mock import patch

from ..tree_diff import main


class MainTest(TestCase):
    @staticmethod
    def _create_file_with_keywords(filename, keywords):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as ofile:
            ofile.write(f'KEYWORDS="{" ".join(keywords)}"')

    @staticmethod
    def _sort_lines(text):
        return '\n'.join(sorted(text.split('\n')))

    def test_success(self):
        with TemporaryDirectory() as old_portdir, TemporaryDirectory() as new_portdir:
            self._create_file_with_keywords(
                os.path.join(old_portdir, 'cat', 'pkg', 'pkg-123.ebuild'), {'x86', '~amd64'})
            self._create_file_with_keywords(
                os.path.join(new_portdir, 'cat', 'pkg', 'pkg-123.ebuild'), {'x86', '~amd64'})
            self._create_file_with_keywords(
                os.path.join(new_portdir, 'cat', 'pkg', 'pkg-456.ebuild'), {'x86', '~amd64'})
            self._create_file_with_keywords(
                os.path.join(new_portdir, 'cat', 'other', 'other-789.ebuild'), {'x86', '~amd64'})

            argv = ['gentoo-tree-diff', '--keywords', '**', old_portdir, new_portdir]
            expected_stdout = dedent("""\
                cat/pkg-456
                cat/other-789
            """)

            with patch('sys.argv', argv), patch('sys.stdout', StringIO()) as stdout_mock:
                main()

            self.assertEqual(self._sort_lines(stdout_mock.getvalue()),
                             self._sort_lines(expected_stdout))
