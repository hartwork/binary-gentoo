# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import heapq
import json
import os
from contextlib import suppress
from typing import List, Set

from .json_formatter import dump_json_for_humans


class PriorityQueue:
    def __init__(self):
        self._push_count = 0
        self._min_heap = []
        self._priority_of = {}

    def _push_to_min_heap(self, prority: float, atom: str):
        item = [prority, self._push_count, atom]
        heapq.heappush(self._min_heap, item)
        self._push_count += 1

    def _remove_from_min_heap(self, atoms: Set[str]) -> Set[str]:
        items = []
        removed_atoms = set()

        while True:
            try:
                item = heapq.heappop(self._min_heap)
            except IndexError:
                break
            else:
                _, _, atom = item
                if atom in atoms:
                    removed_atoms.add(atom)
                    continue
                items.append(item)

        self._min_heap = []
        for item in items:
            heapq.heappush(self._min_heap, item)

        return removed_atoms

    def push(self, priority: float, atom: str):
        if atom in self._priority_of:
            if self._priority_of[atom] <= priority:
                return
            self._remove_from_min_heap({atom})
        self._priority_of[atom] = priority
        self._push_to_min_heap(priority, atom)

    def drop(self, atoms: List[str]):
        for atom in atoms:
            if atom not in self._priority_of:
                raise IndexError(f'Atom {atom!r} not currently in the queue')

        for removed_atom in self._remove_from_min_heap(set(atoms)):
            del self._priority_of[removed_atom]

    def pop(self):
        try:
            prority, _, atom = heapq.heappop(self._min_heap)
        except IndexError:
            raise IndexError('Queue is empty')
        del self._priority_of[atom]
        return atom, prority

    def __iter__(self):
        for item in heapq.nsmallest(len(self._min_heap), self._min_heap):
            yield item[0], item[2]

    def __len__(self):
        return len(self._min_heap)

    @staticmethod
    def load(filename):
        q = PriorityQueue()

        with suppress(FileNotFoundError):
            with open(filename) as f:
                content = f.read()
                if not content:
                    return q

            doc = json.loads(content)

            # TODO proper validation
            assert doc['version'] == 1
            q._min_heap = doc['min_heap']
            q._priority_of = doc['priority_of']
            q._push_count = doc['push_count']

        return q

    def save(self, filename):
        doc = {
            'version': 1,
            'min_heap': self._min_heap,
            'priority_of': self._priority_of,
            'push_count': self._push_count,
        }

        temp_filename = f'{filename}.tmp'

        with open(temp_filename, 'w') as f:
            dump_json_for_humans(doc, f)

        os.rename(temp_filename, filename)
