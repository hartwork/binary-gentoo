# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os.path
from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized

from .._enrich import enrich_host_distdir_of, enrich_host_pkgdir_of, enrich_host_portdir_of


class EnrichTest(TestCase):
    magic_distdir = 'dist123'
    magic_pkgdir = 'pkgdir123'
    magic_portdir = 'portdir123'

    tasks = [
        ('host_distdir', enrich_host_distdir_of, magic_distdir),
        ('host_pkgdir', enrich_host_pkgdir_of, magic_pkgdir),
        ('host_portdir', enrich_host_portdir_of, magic_portdir),
    ]

    @classmethod
    def _fake_portageq(cls, argv):
        if argv == ['portageq', 'pkgdir']:
            path = cls.magic_pkgdir
        elif argv == ['portageq', 'get_repo_path', '/', 'gentoo']:
            path = cls.magic_portdir
        elif argv == ['portageq', 'distdir']:
            path = cls.magic_distdir
        else:
            raise NotImplementedError
        return (path + '\n').encode('ascii')

    @parameterized.expand(tasks)
    def test_with_explicit_path(self, attribute, getter, _):
        magic_relative_filename = 'basename123'
        config_mock = Mock(**{attribute: magic_relative_filename})
        expected_path = os.path.abspath(magic_relative_filename)

        getter(config_mock)

        actual_path = getattr(config_mock, attribute)
        self.assertEqual(actual_path, expected_path)

    @parameterized.expand(tasks)
    def test_without_explicit_path(self, attribute, getter, magic_relative_filename):
        config_mock = Mock(**{attribute: None})
        expected_path = os.path.abspath(magic_relative_filename)

        with patch('subprocess.check_output', self._fake_portageq):
            getter(config_mock)

        actual_path = getattr(config_mock, attribute)
        self.assertEqual(actual_path, expected_path)
