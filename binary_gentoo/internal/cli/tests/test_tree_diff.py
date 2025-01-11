# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os
from contextlib import contextmanager
from io import StringIO
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from ..tree_diff import (
    _replace_special_keywords_for_ebuild,
    enrich_config,
    iterate_new_and_changed_ebuilds,
    main,
    parse_command_line,
)


class ReplaceSpecialKeywordsTest(TestCase):
    @parameterized.expand(
        [
            ("no ops", {"one", "~two"}, {"three", "~four"}, {"one", "~two"}),
            (
                "star op",
                {"one", "~two", "*"},
                {"three", "~four"},
                {"one", "~two", "three"},
            ),
            (
                "tilde star op",
                {"one", "~two", "~*"},
                {"three", "~four"},
                {"one", "~two", "~four"},
            ),
            (
                "double star op",
                {"one", "~two", "**"},
                {"three", "~four"},
                {"one", "~two", "three", "~four"},
            ),
            (
                "start op + tilde star op",
                {"one", "~two", "*", "~*"},
                {"three", "~four"},
                {"one", "~two", "three", "~four"},
            ),
        ]
    )
    def test(self, _, accept_keywords, ebuild_keywords, expected_effective_keywords):
        actual_effective_keywords = _replace_special_keywords_for_ebuild(
            accept_keywords, ebuild_keywords
        )
        self.assertEqual(actual_effective_keywords, expected_effective_keywords)


class EnrichConfigTest(TestCase):
    magic_keywords = "one two ~*"

    @classmethod
    def _fake_subprocess_check_output(cls, argv):
        if argv == ["portageq", "envvar", "ACCEPT_KEYWORDS"]:
            stdout = cls.magic_keywords
        else:
            stdout = f"Hello from: {' '.join(argv)}"
        return (stdout + "\n").encode("ascii")

    def test_given__empty(self):
        config = parse_command_line(["gentoo-tree-diff", "--keywords", "", "dir1", "dir2"])
        with self.assertRaises(ValueError):
            enrich_config(config)

    def test_given__not_empty(self):
        config = parse_command_line(
            ["gentoo-tree-diff", "--keywords", "one    ~two *", "dir1", "dir2"]
        )
        enrich_config(config)
        self.assertEqual(config.keywords, {"one", "two", "~two", "*"})

    def test_not_given__auto_detection(self):
        with patch("binary_gentoo.internal.cli.tree_diff.HOST_IS_GENTOO", True):
            config = parse_command_line(["gentoo-tree-diff", "dir1", "dir2"])
        with (
            patch("subprocess.check_output", self._fake_subprocess_check_output),
            patch("sys.stdout", StringIO()),
        ):
            enrich_config(config)
        self.assertEqual(config.keywords, {"one", "two", "~*"})


class IterateNewAndChangedEbuildsTest(TestCase):
    @classmethod
    @contextmanager
    def _tempdir_config(
        cls,
        keywords: str,
        pessimistic: bool = False,
    ):
        with (
            TemporaryDirectory() as temp_old_portdir,
            TemporaryDirectory() as temp_new_portdir,
        ):
            argv = ["gentoo-tree-diff", "--keywords", keywords]
            if pessimistic:
                argv.append("--pessimistic")
            argv += [temp_old_portdir, temp_new_portdir]

            config = parse_command_line(argv)
            enrich_config(config)

            yield config

    @classmethod
    def _create_ebuild(
        cls,
        portdir,
        ebuild_filename,
        keywords: str = None,
        extra_content: str = None,
    ):
        filename = os.path.join(portdir, ebuild_filename)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            if keywords is not None:
                print(f'KEYWORDS="{keywords}"', file=f)
            if extra_content is not None:
                print(extra_content, file=f)
            f.flush()

    def test_new_live_ebuild_ignored_by_filename(self):
        keywords = "one"
        with self._tempdir_config(keywords=keywords) as config:
            self._create_ebuild(config.new_portdir, "cat/pkg/pkg-123.ebuild", keywords=keywords)
            self._create_ebuild(config.new_portdir, "cat/pkg/pkg-9999.ebuild", keywords=keywords)
            actual_news = list(iterate_new_and_changed_ebuilds(config))
        self.assertEqual(actual_news, ["cat/pkg-123"])

    def test_new_ebuild_without_keyword_line_ignored(self):
        keywords = "one"
        with self._tempdir_config(keywords="one") as config:
            self._create_ebuild(config.new_portdir, "cat/pkg/pkg-123.ebuild", keywords=keywords)
            self._create_ebuild(config.new_portdir, "cat/pkg/pkg-456.ebuild", keywords=None)
            actual_news = list(iterate_new_and_changed_ebuilds(config))
        self.assertEqual(actual_news, ["cat/pkg-123"])

    def test_new_ebuild_without_matching_keyword_ignored(self):
        keywords = "one"
        with self._tempdir_config(keywords="one") as config:
            self._create_ebuild(config.new_portdir, "cat/pkg/pkg-123.ebuild", keywords=keywords)
            self._create_ebuild(config.new_portdir, "cat/pkg/pkg-456.ebuild", keywords="other")
            actual_news = list(iterate_new_and_changed_ebuilds(config))
        self.assertEqual(actual_news, ["cat/pkg-123"])

    def test_unchanged_file_ignored(self):
        keywords = "one"
        ebuild_filename = "cat/pkg/pkg-123.ebuild"
        with self._tempdir_config(keywords=keywords) as config:
            self._create_ebuild(config.old_portdir, ebuild_filename, keywords=keywords)
            self._create_ebuild(config.new_portdir, ebuild_filename, keywords=keywords)
            actual_news = list(iterate_new_and_changed_ebuilds(config))
        self.assertEqual(actual_news, [])

    def test_changed_ebuild_without_matching_keywords_ignored(self):
        keywords = "one"
        ebuild_filename = "cat/pkg/pkg-123.ebuild"
        with self._tempdir_config(keywords="one") as config:
            self._create_ebuild(config.old_portdir, ebuild_filename, keywords=keywords)
            self._create_ebuild(config.new_portdir, ebuild_filename, keywords="other")
            actual_news = list(iterate_new_and_changed_ebuilds(config))
        self.assertEqual(actual_news, [])

    @parameterized.expand(
        [
            ("pessimistic, not ignored", True),
            ("not pessimistic, ignored", False),
        ]
    )
    def test_changed_ebuild_with_matching_identical_keywords(self, _, pessimistic: bool):
        keywords = "one"
        ebuild_filename = "cat/pkg/pkg-123.ebuild"
        with self._tempdir_config(keywords=keywords, pessimistic=pessimistic) as config:
            self._create_ebuild(
                config.old_portdir,
                ebuild_filename,
                keywords=keywords,
                extra_content="# old",
            )
            self._create_ebuild(
                config.new_portdir,
                ebuild_filename,
                keywords=keywords,
                extra_content="# new",
            )
            actual_news = list(iterate_new_and_changed_ebuilds(config))
        expected_news = ["cat/pkg-123"] if pessimistic else []
        self.assertEqual(actual_news, expected_news)

    @parameterized.expand(
        [
            ("pessimistic, not ignored", True),
            ("not pessimistic, not ignored", False),
        ]
    )
    def test_changed_ebuild_with_matching_changed_keywords(self, _, pessimistic: bool):
        ebuild_filename = "cat/pkg/pkg-123.ebuild"
        with self._tempdir_config(keywords="one", pessimistic=pessimistic) as config:
            self._create_ebuild(
                config.old_portdir, ebuild_filename, keywords="~one"
            )  # did not match keywords, previously
            self._create_ebuild(
                config.new_portdir, ebuild_filename, keywords="one"
            )  # just went stable, now matches keywords
            actual_news = list(iterate_new_and_changed_ebuilds(config))
        self.assertEqual(actual_news, ["cat/pkg-123"])


class MainTest(TestCase):
    @staticmethod
    def _create_file_with_keywords(filename, keywords):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as ofile:
            ofile.write(f'KEYWORDS="{" ".join(keywords)}"')

    @staticmethod
    def _sort_lines(text):
        return "\n".join(sorted(text.split("\n")))

    def test_success(self):
        with (
            TemporaryDirectory() as old_portdir,
            TemporaryDirectory() as new_portdir,
        ):
            self._create_file_with_keywords(
                os.path.join(old_portdir, "cat", "pkg", "pkg-123.ebuild"),
                {"x86", "~amd64"},
            )
            self._create_file_with_keywords(
                os.path.join(new_portdir, "cat", "pkg", "pkg-123.ebuild"),
                {"x86", "~amd64"},
            )
            self._create_file_with_keywords(
                os.path.join(new_portdir, "cat", "pkg", "pkg-456.ebuild"),
                {"x86", "~amd64"},
            )
            self._create_file_with_keywords(
                os.path.join(new_portdir, "cat", "other", "other-789.ebuild"),
                {"x86", "~amd64"},
            )

            argv = [
                "gentoo-tree-diff",
                "--keywords",
                "**",
                old_portdir,
                new_portdir,
            ]
            expected_stdout = dedent("""\
                cat/pkg-456
                cat/other-789
            """)

            with (
                patch("sys.argv", argv),
                patch("sys.stdout", StringIO()) as stdout_mock,
            ):
                main()

            self.assertEqual(
                self._sort_lines(stdout_mock.getvalue()),
                self._sort_lines(expected_stdout),
            )
