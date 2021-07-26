# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import fcntl
import heapq
import json
import os
import sys
from argparse import ArgumentParser
from contextlib import contextmanager, suppress
from typing import List, Set

from ..atoms import ATOM_LIKE_DISPLAY
from ..reporter import exception_reporting
from ._parser import add_version_argument_to


def _dump_json_for_humans(obj, fp):
    """Wrapper around ``json.dump`` with custom config"""
    json.dump(obj, fp, indent='  ', sort_keys='True')
    print(file=fp)  # i.e. trailing newline


class MultiQueue:
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
            raise IndexError('All queues are empty')
        del self._priority_of[atom]
        return atom, prority

    def __iter__(self):
        for item in heapq.nsmallest(len(self._min_heap), self._min_heap):
            yield item[0], item[2]

    @staticmethod
    def load(filename):
        muq = MultiQueue()

        with suppress(FileNotFoundError):
            with open(filename) as f:
                doc = json.load(f)

            # TODO proper validation
            assert doc['version'] == 1
            muq._min_heap = doc['min_heap']
            muq._priority_of = doc['priority_of']
            muq._push_count = doc['push_count']

        return muq

    def save(self, filename):
        doc = {
            'version': 1,
            'min_heap': self._min_heap,
            'priority_of': self._priority_of,
            'push_count': self._push_count,
        }

        temp_filename = f'{filename}.tmp'

        with open(temp_filename, 'w') as f:
            _dump_json_for_humans(doc, f)

        os.rename(temp_filename, filename)


@contextmanager
def file_based_interprocess_locking(lock_filename):
    with open(lock_filename, 'w') as lock:
        fcntl.lockf(lock, fcntl.LOCK_EX)  # may block
        try:
            yield
        finally:
            fcntl.lockf(lock, fcntl.LOCK_UN)

            with suppress(FileNotFoundError):
                os.remove(lock_filename)


def run_drop(config):
    muq = MultiQueue.load(config.state_filename)
    muq.drop(config.atoms)
    muq.save(config.state_filename)


def run_push(config):
    muq = MultiQueue.load(config.state_filename)
    for atom in config.atoms:
        muq.push(config.priority, atom)
    muq.save(config.state_filename)


def run_pop(config):
    muq = MultiQueue.load(config.state_filename)
    atom, priority = muq.pop()
    muq.save(config.state_filename)

    doc = {
        'atom': atom,
        'priority': priority,
        'version': 2,
    }

    _dump_json_for_humans(doc, sys.stdout)


def run_show(config):
    muq = MultiQueue.load(config.state_filename)
    for priority_plus_atom in muq:
        priority, atom = priority_plus_atom
        print(priority, atom)


def run(config):
    run_function = {
        'drop': run_drop,
        'pop': run_pop,
        'push': run_push,
        'show': run_show,
    }[config.command]

    with file_based_interprocess_locking(f'{config.state_filename}.lock'):
        run_function(config)


def parse_command_line(argv):
    parser = ArgumentParser(prog='gentoo-local-queue',
                            description='Manages simple file-based push/pop build task queues')

    add_version_argument_to(parser)

    parser.add_argument('--state',
                        metavar='FILENAME',
                        dest='state_filename',
                        default=os.path.expanduser('~/.gentoo-build-queue.json'),
                        help='where to store state (default: "%(default)s")')

    subparsers = parser.add_subparsers(title='sub-cli', dest='command', required=True)

    push_command = subparsers.add_parser('push', description='Add atoms to the queue')
    push_command.add_argument('priority',
                              type=float,
                              metavar='PRIORITY',
                              help='task priority (float, smallest priority wins)')
    push_command.add_argument('atoms',
                              metavar='ATOM',
                              nargs='+',
                              help=f'package atom to push (format "{ATOM_LIKE_DISPLAY}")')

    drop_command = subparsers.add_parser('drop', description='Drop atoms from the queue')
    drop_command.add_argument('atoms',
                              metavar='ATOM',
                              nargs='+',
                              help=f'package atom to drop (format "{ATOM_LIKE_DISPLAY}")')

    subparsers.add_parser('pop', description='Pop atoms from the queue (respecting priority)')

    subparsers.add_parser('show', description='Show queued atoms and their priorities')

    config = parser.parse_args(argv[1:])

    config.state_filename = os.path.realpath(config.state_filename)

    return config


def main():
    with exception_reporting():
        config = parse_command_line(sys.argv)
        run(config)
