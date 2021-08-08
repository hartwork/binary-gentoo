# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from dataclasses import dataclass
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import List
from unittest import TestCase
from unittest.mock import call, patch

from parameterized import parameterized

from ..build import (EmergeTargetType, classify_emerge_target, enrich_config, main,
                     parse_command_line)


@dataclass
class RunRecord:
    call_args_list: List["call"]


class ClassifyEmergeTargetTest(TestCase):
    @parameterized.expand([
        ('cat/pkg', (EmergeTargetType.PACKAGE, 'cat', 'pkg')),
        ('cat/pkg-123', (EmergeTargetType.PACKAGE, 'cat', 'pkg')),
        ('=cat/pkg-123', (EmergeTargetType.PACKAGE, 'cat', 'pkg')),
        ('@world', (EmergeTargetType.SET, 'sets', '@world')),
    ])
    def test_wellformed(self, candidate, expected_tuple):
        actual_tuple = classify_emerge_target(candidate)
        self.assertEqual(actual_tuple, expected_tuple)

    @parameterized.expand([
        ('', ValueError),
        ('not a set, not an atom', ValueError),
        (None, TypeError),
    ])
    def test_malformed(self, candidate, expected_exception):
        with self.assertRaises(expected_exception):
            classify_emerge_target(candidate)


class EnrichConfigTest(TestCase):
    magic_profile = 'default/linux/profile123'
    magic_cflags = 'cflags123'
    magic_cxxflags = 'cxxflags123'
    magic_ldflags = 'ldflags123'
    magic_cpu_flags_x86 = 'cpuflags123'

    @classmethod
    def _fake_subprocess_check_output(cls, argv):
        if argv == ['eselect', 'profile', 'show']:
            output = dedent(f"""\
                Current /etc/portage/make.profile symlink:
                  {cls.magic_profile}""")
        elif argv == ['portageq', 'envvar', 'CFLAGS']:
            output = cls.magic_cflags
        elif argv == ['portageq', 'envvar', 'CXXFLAGS']:
            output = cls.magic_cxxflags
        elif argv == ['portageq', 'envvar', 'LDFLAGS']:
            output = cls.magic_ldflags
        elif argv == ['portageq', 'envvar', 'CPU_FLAGS_X86']:
            output = cls.magic_cpu_flags_x86
        else:
            output = f'Hello from: {" ".join(argv)}'
        return (output + '\n').encode('ascii')

    def test_portagq_interaction(self):
        config = parse_command_line(['gentoo-build', 'cat/pkg'])

        with patch('subprocess.check_output', self._fake_subprocess_check_output):
            enrich_config(config)

        self.assertEqual(config.gentoo_profile, self.magic_profile)
        self.assertEqual(config.cflags, self.magic_cflags)
        self.assertEqual(config.cxxflags, self.magic_cxxflags)
        self.assertEqual(config.ldflags, self.magic_ldflags)
        self.assertEqual(config.cpu_flags_x86, self.magic_cpu_flags_x86)


class MainTest(TestCase):
    @staticmethod
    def _run_gentoo_build_with_subprocess_mocked(argv_extra: List[str] = None) -> RunRecord:
        if argv_extra is None:
            argv_extra = []

        with TemporaryDirectory() as temp_distdir,\
                TemporaryDirectory() as temp_pkgdir,\
                TemporaryDirectory() as temp_portdir, \
                TemporaryDirectory() as temp_logdir:
            argv = [
                'gentoo-build',
                '--distdir',
                temp_distdir,
                '--pkgdir',
                temp_pkgdir,
                '--portdir',
                temp_portdir,
                '--logdir',
                temp_logdir,
                '--gentoo-profile',
                'default/linux/profile123',
                '--cflags',
                'cflags123',
                '--cxxflags',
                'cxxflags123',
                '--ldflags',
                'ldflags123',
                '--cpu-flags-x86',
                'cpuflags123',
            ] + argv_extra + [
                '=cat/pkg-123',
            ]

            with patch('sys.argv', argv), patch('subprocess.check_call') as check_call_mock:
                main()

            return RunRecord(call_args_list=check_call_mock.call_args_list, )

    def test_success_invokes_rsync_and_docker(self):
        run_record = self._run_gentoo_build_with_subprocess_mocked()

        rsync_call = run_record.call_args_list[0]
        self.assertEqual(rsync_call.args[0][0], 'rsync')

        docker_run_call = run_record.call_args_list[1]
        self.assertEqual(docker_run_call.args[0][:2], ['docker', 'run'])

        self.assertEqual(len(run_record.call_args_list), 2)

    def test_argument__tag_docker_image_invokes_docker_commit(self):
        run_record = self._run_gentoo_build_with_subprocess_mocked(argv_extra=[
            '--tag-docker-image',
            'image123',
        ])

        docker_commit_call = run_record.call_args_list[2]
        self.assertEqual(docker_commit_call.args[0][:2], ['docker', 'commit'])

        docker_rm_call = run_record.call_args_list[3]
        self.assertEqual(docker_rm_call.args[0][:2], ['docker', 'rm'])

        self.assertEqual(len(run_record.call_args_list), 4)

    @parameterized.expand([
        (['--update'], '--update'),
        (['--use', 'mp3 png'], "USE='mp3 png'"),
    ])
    def test_fordwarding_to_emerge(self, argv_extra, container_command_needle):
        for argv_extra, assertion in (
            (argv_extra, self.assertIn),
            ([], self.assertNotIn),
        ):
            run_record = self._run_gentoo_build_with_subprocess_mocked(argv_extra=argv_extra)

            docker_run_call = run_record.call_args_list[1]
            self.assertEqual(docker_run_call.args[0][:2], ['docker', 'run'])  # self-test
            container_command_haystack = docker_run_call.args[0][-1]

            assertion(container_command_needle, container_command_haystack)
