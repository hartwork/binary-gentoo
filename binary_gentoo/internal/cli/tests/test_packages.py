# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os
from io import StringIO
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase
from unittest.mock import Mock, patch

from freezegun import freeze_time
from parameterized import parameterized

from ..packages import (adjust_index_file_header, has_safe_package_path, main, parse_package_block,
                        read_packages_index_file, run_delete, run_list)


class ParsePackageBlockTest(TestCase):
    _REALISTIC_PACKAGE_BLOCK_WITHOUT_PATH = dedent("""\
        BDEPEND: dev-util/gdbus-codegen dev-util/intltool virtual/pkgconfig sys-devel/gettext x11-base/xorg-proto
        BUILD_ID: 1
        BUILD_TIME: 1625051237
        CPV: xfce-base/xfce4-settings-4.16.2
        DEFINED_PHASES: configure postinst postrm setup
        DEPEND: dev-lang/python:3.8 >=dev-lang/python-exec-2:2/2=[python_targets_python3_8] >=dev-libs/glib-2.50 media-libs/fontconfig >=x11-libs/gtk+-3.20:3 x11-libs/libX11 >=x11-libs/libXcursor-1.1 >=x11-libs/libXi-1.3 >=x11-libs/libXrandr-1.2 >=xfce-base/garcon-0.2:0/0= >=xfce-base/exo-4.15.1:0/0= >=xfce-base/libxfce4ui-4.15.1:0/0= >=xfce-base/libxfce4util-4.15.2:0/7= >=xfce-base/xfconf-4.13:0/3= >=x11-libs/libnotify-0.7 >=sys-power/upower-0.9.23 >=x11-libs/libxklavier-5 !<xfce-base/exo-4.15.1
        EAPI: 7
        IUSE: colord input_devices_libinput libcanberra libnotify upower +xklavier python_single_target_python3_8 python_single_target_python3_9
        KEYWORDS: ~alpha ~amd64 ~arm ~arm64 ~hppa ~ia64 ~mips ~ppc ~ppc64 ~riscv ~sparc ~x86 ~amd64-linux ~x86-linux
        LICENSE: GPL-2+
        MD5: 690ff036d8df49a07e97f4fad7b85737
        PROVIDES: x86_64: xfce4-accessibility-settings.debug xfce4-appearance-settings.debug xfce4-display-settings.debug xfce4-find-cursor.debug xfce4-keyboard-settings.debug xfce4-mime-helper.debug xfce4-mime-settings.debug xfce4-mouse-settings.debug xfce4-settings-editor.debug xfce4-settings-manager.debug xfsettingsd.debug
        RDEPEND: dev-lang/python:3.8 >=dev-lang/python-exec-2:2/2=[python_targets_python3_8] >=dev-libs/glib-2.50 media-libs/fontconfig >=x11-libs/gtk+-3.20:3 x11-libs/libX11 >=x11-libs/libXcursor-1.1 >=x11-libs/libXi-1.3 >=x11-libs/libXrandr-1.2 >=xfce-base/garcon-0.2:0/0= >=xfce-base/exo-4.15.1:0/0= >=xfce-base/libxfce4ui-4.15.1:0/0= >=xfce-base/libxfce4util-4.15.2:0/7= >=xfce-base/xfconf-4.13:0/3= >=x11-libs/libnotify-0.7 >=sys-power/upower-0.9.23 >=x11-libs/libxklavier-5 !<xfce-base/exo-4.15.1
        REQUIRES: x86_64: libX11.so.6 libXcursor.so.1 libXi.so.6 libXrandr.so.2 libatk-1.0.so.0 libc.so.6 libcairo.so.2 libexo-2.so.0 libfontconfig.so.1 libgarcon-1.so.0 libgdk-3.so.0 libgdk_pixbuf-2.0.so.0 libgio-2.0.so.0 libglib-2.0.so.0 libgobject-2.0.so.0 libgtk-3.so.0 libm.so.6 libnotify.so.4 libpango-1.0.so.0 libpangocairo-1.0.so.0 libpthread.so.0 libupower-glib.so.3 libxfce4kbd-private-3.so.0 libxfce4ui-2.so.0 libxfce4util.so.7 libxfconf-0.so.3 libxklavier.so.16
        SHA1: 1a6578f07c4bbf47d227b63f60eaf0c4a65c5212
        SIZE: 1356565
        USE: abi_x86_64 amd64 elibc_glibc kernel_linux libnotify python_single_target_python3_8 upower userland_GNU xklavier
        MTIME: 1625051239
        REPO: gentoo
    """)  # noqa: E501
    _DUMMY_PACKAGE_BLOCK_WITH_PATH = dedent("""\
        BUILD_ID: 123
        BUILD_TIME: 123
        CPV: cat/pkg-123
        PATH: cat/pkg/pkg-123-1.xpak
    """)

    def test_extraction(self):
        package = parse_package_block(self._REALISTIC_PACKAGE_BLOCK_WITHOUT_PATH)
        self.assertEqual(package.full_name, 'xfce-base/xfce4-settings-4.16.2-1')
        self.assertEqual(package.build_time, 1625051237)
        self.assertEqual(package.cpv, 'xfce-base/xfce4-settings-4.16.2')

    def test_contained_path_retrieved(self):
        package = parse_package_block(self._REALISTIC_PACKAGE_BLOCK_WITHOUT_PATH)
        self.assertEqual(package.path, 'xfce-base/xfce4-settings-4.16.2.tbz2')

    def test_missing_path_inferred(self):
        package = parse_package_block(self._DUMMY_PACKAGE_BLOCK_WITH_PATH)
        self.assertEqual(package.path, 'cat/pkg/pkg-123-1.xpak')


class AdjustIndexFileHeaderTest(TestCase):
    def test_replacement(self):
        original_dummy_header = dedent("""\
            PACKAGES: 758
            TIMESTAMP: 1627149542
            VERSION: 0
        """)
        new_package_count = 123
        new_modification_timestamp = 999999999999999  # some int bigger than current epoch seconds
        expected_header = dedent(f"""\
            PACKAGES: {new_package_count}
            TIMESTAMP: {new_modification_timestamp}
            VERSION: 0
        """)
        actual_header = adjust_index_file_header(
            old_header=original_dummy_header,
            new_package_count=new_package_count,
            new_modification_timestamp=new_modification_timestamp)
        self.assertEqual(actual_header, expected_header)


class HasSafePackagePathTest(TestCase):
    @parameterized.expand([
        ('cat/pkg/pkg-123-1.xpak', True, 'healthy .xpak'),
        ('cat/pkg-123.tbz2', True, 'healthy .tbz2'),
        ('../pkg-123.tbz2', False, 'bad ..'),
        ('/cat/pkg-123.tbz2', False, 'bad leading slash'),
    ])
    def test(self, candidate_path, expected_is_safe, _comment):
        package_mock = Mock(path=candidate_path)
        actual_is_safe = has_safe_package_path(package_mock)
        self.assertEqual(actual_is_safe, expected_is_safe)


class ReadPackagesIndexFileTest(TestCase):
    def test_success(self):
        expected_header = 'K1: v1'
        expected_packages_blocks = ['K2: v2', 'K3: v3', '']

        with TemporaryDirectory() as tempdir:
            expected_packages_index_filename = os.path.join(tempdir, 'Packages')
            with open(expected_packages_index_filename, 'w') as f:
                flat_packages_blocks = "\n\n".join(expected_packages_blocks)
                print(f'{expected_header}\n\n{flat_packages_blocks}', end='', file=f)
            config_mock = Mock(host_pkgdir=tempdir)

            actual_header, actual_packages_blocks, actual_packages_index_filename \
                = read_packages_index_file(config_mock)

        self.assertEqual(actual_header, expected_header)
        self.assertEqual(actual_packages_blocks, expected_packages_blocks)
        self.assertEqual(actual_packages_index_filename, expected_packages_index_filename)


class RunDeleteTest(TestCase):
    @staticmethod
    def _create_empty_file(filename):
        os.makedirs(os.path.dirname(filename))
        with open(filename, 'w'):
            pass

    @parameterized.expand([
        ('pretend', True),
        ('actually delete files', False),
    ])
    def test_success(self, _label, pretend):
        original_dummy_index_content = dedent("""\
            PACKAGES: 2
            TIMESTAMP: 123
            VERSION: 0

            BUILD_ID: 1
            BUILD_TIME: 1
            CPV: one/one-1

            BUILD_ID: 2
            BUILD_TIME: 2
            CPV: two/two-2

        """)
        now_epoch_seconds = 456
        expected_post_deletion_index_content = dedent(f"""\
            PACKAGES: 1
            TIMESTAMP: {now_epoch_seconds}
            VERSION: 0

            BUILD_ID: 2
            BUILD_TIME: 2
            CPV: two/two-2

        """)

        with TemporaryDirectory() as tempdir:
            binary_path_one = os.path.join(tempdir, 'one/one-1.tbz2')
            binary_path_two = os.path.join(tempdir, 'two/two-2.tbz2')

            with open(os.path.join(tempdir, 'Packages'), 'w') as f:
                print(original_dummy_index_content, end='', file=f)
            self._create_empty_file(binary_path_one)
            self._create_empty_file(binary_path_two)

            # This will delete the first of the two packages
            config_mock = Mock(
                host_pkgdir=tempdir,
                metadata='BUILD_TIME: 1',
                pretend=pretend,
            )

            time_mock = Mock(return_value=float(now_epoch_seconds))
            with patch('time.time', time_mock):
                run_delete(config_mock)

            with open(os.path.join(tempdir, 'Packages')) as f:
                actual_post_deletion_index_content = f.read()

            if pretend:
                self.assertTrue(os.path.exists(binary_path_one))
                self.assertTrue(os.path.exists(binary_path_two))
                self.assertEqual(actual_post_deletion_index_content, original_dummy_index_content)
            else:
                self.assertFalse(os.path.exists(binary_path_one))
                self.assertTrue(os.path.exists(binary_path_two))
                self.assertEqual(actual_post_deletion_index_content,
                                 expected_post_deletion_index_content)


class RunListTest(TestCase):
    @staticmethod
    def _run_list_with_config(config):
        with patch('sys.stdout', StringIO()) as stdout_mock:
            run_list(config)
        return stdout_mock.getvalue()

    def test_success__sorted_by_build_time(self):
        dummy_index_content = dedent("""\
            VERSION: 0

            BUILD_ID: 2
            BUILD_TIME: 2
            CPV: two/two-2

            BUILD_ID: 1
            BUILD_TIME: 1
            CPV: one/one-1

        """)
        expected_stdout__summary = dedent("""\
            [1970-01-01 04:00:01] one/one-1-1
            [1970-01-01 04:00:02] two/two-2-2
        """)
        expected_stdout__atoms = dedent("""\
            =one/one-1
            =two/two-2
        """)

        with TemporaryDirectory() as tempdir:
            config_mock = Mock(atoms=False, host_pkgdir=tempdir)
            with open(os.path.join(tempdir, 'Packages'), 'w') as f:
                print(dummy_index_content, end='', file=f)

            with freeze_time(tz_offset=4):
                actual_stdout__summary = self._run_list_with_config(config_mock)
            self.assertEqual(actual_stdout__summary, expected_stdout__summary)

            config_mock.atoms = True

            actual_stdout__atoms = self._run_list_with_config(config_mock)
            self.assertEqual(actual_stdout__atoms, expected_stdout__atoms)


class MainTest(TestCase):
    @parameterized.expand([
        ('gentoo-packages', '--help'),
        ('gentoo-packages', 'delete', '--help'),
        ('gentoo-packages', 'list', '--help'),
    ])
    def test_help(self, *argv):  # plain smoke test
        with patch('sys.argv', argv), patch('sys.stdout', StringIO()) as stdout_mock:
            with self.assertRaises(SystemExit) as catcher:
                main()
            self.assertEqual(catcher.exception.args, (0, ))  # i.e. success
            self.assertIn('optional arguments:', stdout_mock.getvalue())

    def test_list_failure_empty_directory(self):  # just something that touches beyond argparse
        with TemporaryDirectory() as tempdir:
            argv = ['gentoo-packages', '--pkgdir', tempdir, 'list']
            with patch('sys.argv', argv), self.assertRaises(SystemExit) as catcher:
                main()
            self.assertEqual(catcher.exception.args, (1, ))  # i.e. error
