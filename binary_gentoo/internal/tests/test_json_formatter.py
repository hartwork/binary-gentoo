# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from io import StringIO
from textwrap import dedent
from unittest import TestCase

from binary_gentoo.internal.json_formatter import dump_json_for_humans


class DumpJsonForHumansTest(TestCase):
    def test_healthy_formatting(self):
        doc = {
            'k1': 'v1',
            'k2': 'v2',
        }
        memory_file = StringIO()

        dump_json_for_humans(doc, memory_file)

        self.assertEqual(
            memory_file.getvalue(),
            dedent("""\
            {
              "k1": "v1",
              "k2": "v2"
            }
        """))
