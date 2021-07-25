# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import call, patch

from ..clean import main


class MainTest(TestCase):
    def test_success(self):
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

            expected_container_argv_flat = ' && '.join([
                'eclean-pkg --time-limit=30d --interactive',
                'eclean-dist --time-limit=30d --interactive',
            ])
            expected_docker_argv = [
                'docker',
                'run',
                '-it',
                '--rm',
                '-v',
                f'{temp_portdir}:/var/db/repos/gentoo:ro',
                '-v',
                f'{temp_pkgdir}:/var/cache/binpkgs:rw',
                '-v',
                f'{temp_distdir}:/var/cache/distfiles:rw',
                'hartwork/gentoo-stage3-plus-gentoolkit',
                'sh',
                '-c',
                expected_container_argv_flat,
            ]
            expected_call = call(expected_docker_argv, stdout=None)

            with patch('sys.argv', argv), patch('subprocess.check_call') as check_call_mock:
                main()

            self.assertEqual(check_call_mock.call_args.call_list(), [expected_call])
