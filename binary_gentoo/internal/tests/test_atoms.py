# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from unittest import TestCase

from parameterized import parameterized

from ..atoms import extract_category_package_from


class ExtractCategoryPackageFromTest(TestCase):
    @parameterized.expand([
        ('dev-util/meld', 'dev-util', 'meld'),
        ('dev-util/meld-3.20.3-r1', 'dev-util', 'meld'),
        ('=dev-util/meld-3.20.3-r1', 'dev-util', 'meld'),
        ('x11-libs/gtk+', 'x11-libs', 'gtk+'),
        ('x11-libs/gtk+-3.24.29', 'x11-libs', 'gtk+'),
        ('cross-i686-w64-mingw32/binutils-2.35.2', 'cross-i686-w64-mingw32', 'binutils'),
    ])
    def test_success(self, candidate, expected_category, expected_package):
        self.assertEqual(extract_category_package_from(candidate),
                         (expected_category, expected_package))

    @parameterized.expand([
        ('not valid syntax', ValueError),
        (None, TypeError),
    ])
    def test_failure(self, candidate, expected_exception_class):
        with self.assertRaises(expected_exception_class):
            extract_category_package_from(candidate)
