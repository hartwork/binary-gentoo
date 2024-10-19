# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from dataclasses import dataclass
from io import StringIO
from subprocess import call
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from ..tree_sync import main


@dataclass
class RunRecord:
    call_args_list: list["call"]


class MainTest(TestCase):
    @staticmethod
    def _run_gentoo_tree_sync_with_subprocess_mocked(backup: bool) -> RunRecord:
        with (
            TemporaryDirectory() as temp_portdir_old,
            TemporaryDirectory() as temp_portdir_new,
        ):
            argv = ["gentoo-tree-sync"]
            if backup:
                argv += ["--backup-to", temp_portdir_old]
            argv.append(temp_portdir_new)

            with (
                patch("sys.argv", argv),
                patch("subprocess.check_call") as check_call_mock,
                patch("sys.stdout", StringIO()),
            ):
                main()

            return RunRecord(
                call_args_list=check_call_mock.call_args_list,
            )

    @parameterized.expand(
        [
            ("with backup", True),
            ("without backup", False),
        ]
    )
    def test_success_invokes_docker(self, _, backup: bool):
        run_record = self._run_gentoo_tree_sync_with_subprocess_mocked(backup=backup)

        docker_run_call = run_record.call_args_list[0]
        self.assertEqual(docker_run_call.args[0][:2], ["docker", "run"])

        self.assertEqual(len(run_record.call_args_list), 1)
