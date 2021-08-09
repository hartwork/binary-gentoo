# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os
import sys
from argparse import ArgumentParser

from ..atoms import ATOM_LIKE_DISPLAY
from ..fs_lock import file_based_interprocess_locking
from ..json_formatter import dump_json_for_humans
from ..priority_queue import PriorityQueue
from ..reporter import exception_reporting
from ._parser import add_version_argument_to


def run_drop(config):
    q = PriorityQueue.load(config.state_filename)
    q.drop(config.atoms)
    q.save(config.state_filename)


def run_push(config):
    q = PriorityQueue.load(config.state_filename)
    for atom in config.atoms:
        q.push(config.priority, atom)
    q.save(config.state_filename)


def run_pop(config):
    q = PriorityQueue.load(config.state_filename)
    atom, priority = q.pop()
    q.save(config.state_filename)

    doc = {
        'atom': atom,
        'priority': priority,
        'version': 2,
    }

    dump_json_for_humans(doc, sys.stdout)


def run_show(config):
    q = PriorityQueue.load(config.state_filename)
    for priority_plus_atom in q:
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
