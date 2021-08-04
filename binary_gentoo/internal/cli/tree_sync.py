# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os
import shlex
import sys
from argparse import ArgumentParser

from ..reporter import announce_and_call, exception_reporting
from ._parser import (add_docker_image_argument_to, add_interactive_argument_to,
                      add_version_argument_to)


def parse_command_line(argv):
    parser = ArgumentParser(prog='gentoo-tree-sync',
                            description='Brings a given portdir (and its backup) up to date')

    add_version_argument_to(parser)

    add_interactive_argument_to(parser)

    add_docker_image_argument_to(parser)

    # NOTE: Unlike enrich_host_portdir_of(..), this variant does not do auto-detection
    #       based on portageq
    parser.add_argument('host_portdir',
                        metavar='DIR',
                        help=('location for PORTDIR'
                              ' (e.g. "/var/db/repos/gentoo" or "/usr/portage")'))

    parser.add_argument('--backup-to',
                        dest='host_backup_portdir',
                        metavar='DIR',
                        help=('location to backup original state of PORTDIR to'
                              ' (e.g. "/var/db/repos/gentoo-old" or "/usr/portage-old")'
                              ' prior to synchronisation (using "rsync --archive --delete [..]")'))

    config = parser.parse_args(argv[1:])

    config.host_portdir = os.path.realpath(config.host_portdir)

    if config.host_backup_portdir is not None:
        config.host_backup_portdir = os.path.realpath(config.host_backup_portdir)

    return config


def _with_trailing_slash(text):
    return text.rstrip('/') + '/'


def sync(config):
    container_portdir = '/usr/portage'
    container_backup_portdir = '/mnt/portage-backup'

    container_command = [
        'set -x',
    ]

    if config.host_backup_portdir:
        rsync_argv = [
            'rsync',
            '--archive',
            '--delete',
            '--verbose',
            '--progress',
            _with_trailing_slash(container_portdir),
            _with_trailing_slash(container_backup_portdir),
        ]
        rsync_command = ' '.join(shlex.quote(a) for a in rsync_argv)
        container_command.append(rsync_command)

    container_command += [
        # This will suppress the warning about an invalid profile
        # by giving symlink /etc/portage/make.profile (that currently points to
        # non-existing "../../var/db/repos/gentoo/profiles/[..]") a valid target
        f'ln -s {shlex.quote(container_portdir)} /var/db/repos/gentoo',
        f'env PORTDIR={shlex.quote(container_portdir)} emerge-webrsync --verbose',
    ]

    container_command_flat = ' && '.join(container_command)

    docker_volume_args = ['-v', f'{config.host_portdir}:{container_portdir}:rw']
    if config.host_backup_portdir:
        docker_volume_args += ['-v', f'{config.host_backup_portdir}:{container_backup_portdir}:rw']

    docker_run_args = [
        '--rm',
    ] + docker_volume_args + [
        config.docker_image,
        'sh',
        '-c',
        container_command_flat,
    ]

    if config.interactive:
        docker_run_args = ['-it'] + docker_run_args

    announce_and_call(['docker', 'run'] + docker_run_args)


def main():
    with exception_reporting():
        config = parse_command_line(sys.argv)
        sync(config)


if __name__ == '__main__':
    main()
