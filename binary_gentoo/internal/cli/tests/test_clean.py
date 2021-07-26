# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from dataclasses import dataclass
from itertools import product
from tempfile import TemporaryDirectory
from typing import List
from unittest import TestCase
from unittest.mock import call, patch

from parameterized import parameterized

from ..clean import main


@dataclass
class RunRecord:
    temp_distdir: str
    temp_pkgdir: str
    temp_portdir: str
    call_args_list: List["call"]


class MainTest(TestCase):
    @staticmethod
    def _run_gentoo_clean_with_subprocess_mocked(pretend=False, interactive=True) -> RunRecord:
        with TemporaryDirectory() as temp_distdir,\
                TemporaryDirectory() as temp_pkgdir,\
                TemporaryDirectory() as temp_portdir:
            argv = [
                'gentoo-clean',
                '--distdir',
                temp_distdir,
                '--pkgdir',
                temp_pkgdir,
                '--portdir',
                temp_portdir,
            ]

            if pretend:
                argv.append('--pretend')
            if not interactive:
                argv.append('--non-interactive')

            with patch('sys.argv', argv), patch('subprocess.check_call') as check_call_mock:
                main()

            return RunRecord(
                temp_distdir=temp_distdir,
                temp_pkgdir=temp_pkgdir,
                temp_portdir=temp_portdir,
                call_args_list=check_call_mock.call_args_list,
            )

    @parameterized.expand(product(['interactive', 'pretend'], [True, False]))
    def test_argument_forwarded_to_eclean(self, key, value):
        run_record = self._run_gentoo_clean_with_subprocess_mocked(**{key: value})

        docker_run_call = run_record.call_args_list[0]
        container_argv_flat = docker_run_call.args[0][-1]
        self.assertEqual(container_argv_flat.count(f' --{key}'), 2 if value else 0)

    def test_docker_mounts_fine(self):
        run_record = self._run_gentoo_clean_with_subprocess_mocked()

        docker_run_call = run_record.call_args_list[0]
        expected_mounts = [
            f'{run_record.temp_portdir}:/var/db/repos/gentoo:ro',
            f'{run_record.temp_pkgdir}:/var/cache/binpkgs:rw',
            f'{run_record.temp_distdir}:/var/cache/distfiles:rw',
        ]
        for expected_mount in expected_mounts:
            self.assertIn(expected_mount, docker_run_call.args[0])
