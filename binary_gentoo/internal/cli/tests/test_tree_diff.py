# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os
from io import StringIO
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from ..tree_diff import (_replace_special_keywords_for_ebuild, enrich_config, main,
                         parse_command_line)


class ReplaceSpecialKeywordsTest(TestCase):
    @parameterized.expand([
        ('no ops', {'one', '~two'}, {'three', '~four'}, {'one', '~two'}),
        ('star op', {'one', '~two', '*'}, {'three', '~four'}, {'one', '~two', 'three'}),
        ('tilde star op', {'one', '~two', '~*'}, {'three', '~four'}, {'one', '~two', '~four'}),
        ('double star op', {'one', '~two', '**'}, {'three',
                                                   '~four'}, {'one', '~two', 'three', '~four'}),
        ('start op + tilde star op', {'one', '~two', '*',
                                      '~*'}, {'three', '~four'}, {'one', '~two', 'three',
                                                                  '~four'}),
    ])
    def test(self, _, accept_keywords, ebuild_keywords, expected_effective_keywords):
        actual_effective_keywords = _replace_special_keywords_for_ebuild(
            accept_keywords, ebuild_keywords)
        self.assertEqual(actual_effective_keywords, expected_effective_keywords)


class EnrichConfigTest(TestCase):
    magic_keywords = 'one two ~*'

    @classmethod
    def _fake_subprocess_check_output(cls, argv):
        if argv == ['portageq', 'envvar', 'ACCEPT_KEYWORDS']:
            stdout = cls.magic_keywords
        else:
            stdout = f'Hello from: {" ".join(argv)}'
        return (stdout + '\n').encode('ascii')

    def test_given__empty(self):
        config = parse_command_line(['gentoo-tree-diff', '--keywords', '', 'dir1', 'dir2'])
        with self.assertRaises(ValueError):
            enrich_config(config)

    def test_given__not_empty(self):
        config = parse_command_line(
            ['gentoo-tree-diff', '--keywords', 'one    ~two *', 'dir1', 'dir2'])
        enrich_config(config)
        self.assertEqual(config.keywords, {'one', 'two', '~two', '*'})

    def test_not_given__auto_detection(self):
        config = parse_command_line(['gentoo-tree-diff', 'dir1', 'dir2'])
        with patch('subprocess.check_output', self._fake_subprocess_check_output):
            enrich_config(config)
        self.assertEqual(config.keywords, {'one', 'two', '~*'})


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
