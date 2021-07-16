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
                            description='Brings a given portdir up to date')

    add_version_argument_to(parser)

    add_interactive_argument_to(parser)

    add_docker_image_argument_to(parser)

    # NOTE: Unlike enrich_host_portdir_of(..), this variant does not do auto-detection
    #       based on portageq
    parser.add_argument('host_portdir',
                        metavar='DIR',
                        help=('location for PORTDIR'
                              ' (e.g. "/var/db/repos/gentoo" or "/usr/portage")'))

    config = parser.parse_args(argv[1:])

    config.host_portdir = os.path.realpath(config.host_portdir)

    return config


def sync(config):
    container_portdir = '/usr/portage'

    container_command_flat = ' && '.join([
        # This will fix /etc/portage/make.profile
        # and hence suppress the warning about an invalid profile
        f'ln -s {shlex.quote(container_portdir)} /var/db/repos/gentoo',
        f'env PORTDIR={shlex.quote(container_portdir)} emerge-webrsync --verbose',
    ])

    docker_run_args = [
        '--rm',
        '-v',
        f'{config.host_portdir}:{container_portdir}:rw',
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
