# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from textwrap import dedent
from unittest import TestCase

from ..packages import adjust_index_file_header, parse_package_block


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
