# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import json
from tempfile import NamedTemporaryFile
from unittest import TestCase

from parameterized import parameterized

from ..json_formatter import dump_json_for_humans
from ..priority_queue import PriorityQueue


class PushTest(TestCase):
    def test_sorted_by_priority(self):
        q = PriorityQueue()
        q.push(1.0, 'cat/pkg-one')
        q.push(3.0, 'cat/pkg-three')
        q.push(2.0, 'cat/pkg-two')

        self.assertEqual(list(q), [
            (1.0, 'cat/pkg-one'),
            (2.0, 'cat/pkg-two'),
            (3.0, 'cat/pkg-three'),
        ])

    @parameterized.expand([
        # NOTE: Priority can only be decreased, not increased
        ([1.0, 2.0, 3.0], 1.0),
        ([3.0, 2.0, 4.0], 2.0),
    ])
    def test_adjusting_priority(self, priorities, expected_priority):
        atom = 'cat/pkg-one'
        q = PriorityQueue()
        for priority in priorities:
            q.push(priority, atom)

        self.assertEqual(list(q), [
            (expected_priority, atom),
        ])


class PopTest(TestCase):
    def test_empty(self):
        with self.assertRaises(IndexError) as catcher:
            PriorityQueue().pop()
        self.assertEqual(str(catcher.exception), 'Queue is empty')

    def test_not_empty__lowest_priority(self):
        q = PriorityQueue()
        q.push(3.0, 'cat/pkg-three')
        q.push(1.0, 'cat/pkg-one')
        q.push(2.0, 'cat/pkg-two')
        self.assertEqual(len(q), 3)

        popped = q.pop()

        self.assertEqual(len(q), 2)
        self.assertEqual(popped, ('cat/pkg-one', 1.0))


class DropTest(TestCase):
    def test_existing__success(self):
        q = PriorityQueue()
        q.push(1.0, 'cat/pkg-one')
        q.push(2.0, 'cat/pkg-two')
        q.push(3.0, 'cat/pkg-three')
        self.assertEqual(len(q), 3)

        q.drop(['cat/pkg-one', 'cat/pkg-three'])

        self.assertEqual(len(q), 1)

    def test_non_existing__raises(self):
        q = PriorityQueue()
        q.push(1.0, 'cat/pkg-one')
        self.assertEqual(len(q), 1)

        with self.assertRaises(IndexError):
            q.drop(['cat/pkg-two', 'cat/pkg-three'])

        self.assertEqual(len(q), 1)

    def test_mixed__is_atomic(self):
        q = PriorityQueue()
        q.push(1.0, 'cat/pkg-one')
        q.push(2.0, 'cat/pkg-two')
        self.assertEqual(len(q), 2)

        with self.assertRaises(IndexError):
            q.drop(['cat/pkg-one', 'cat/pkg-three'])

        self.assertEqual(len(q), 2)


class LoadSaveTest(TestCase):
    expected_loaded = [
        (1.0, 'cat/pkg-one'),
        (2.0, 'cat/pkg-two'),
    ]
    expected_saved = {
        'min_heap': [[1.0, 0, 'cat/pkg-one'], [2.0, 1, 'cat/pkg-two']],
        'priority_of': {
            'cat/pkg-one': 1.0,
            'cat/pkg-two': 2.0,
        },
        'push_count': 2,
        'version': 1,
    }

    def test_load(self):
        with NamedTemporaryFile(mode='w') as f:
            dump_json_for_humans(self.expected_saved, f)
            f.flush()
            q = PriorityQueue.load(f.name)

        self.assertEqual(list(q), self.expected_loaded)

    def test_save(self):
        q = PriorityQueue()
        for priority, atom in self.expected_loaded:
            q.push(priority, atom)

        with NamedTemporaryFile() as f:
            q.save(f.name)
            with open(f.name) as f:  # re-open needed to due to file rename in .save
                doc = json.load(f)

        self.assertEqual(doc, self.expected_saved)
