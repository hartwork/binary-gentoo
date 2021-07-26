# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import shlex
import sys
from argparse import ArgumentParser

from ..reporter import announce_and_call, exception_reporting
from ._enrich import enrich_host_distdir_of, enrich_host_pkgdir_of, enrich_host_portdir_of
from ._parser import (add_distdir_argument_to, add_docker_image_argument_to,
                      add_interactive_argument_to, add_pkgdir_argument_to, add_portdir_argument_to,
                      add_version_argument_to)


def parse_command_line(argv):
    parser = ArgumentParser(prog='gentoo-package-clean',
                            description='Clean Gentoo pkgdir/distdir files'
                            ' using eclean of app-portage/gentoolkit'
                            ' with Docker isolation')

    add_version_argument_to(parser)

    add_portdir_argument_to(parser)
    add_pkgdir_argument_to(parser)
    add_distdir_argument_to(parser)

    add_interactive_argument_to(parser)

    add_docker_image_argument_to(parser, default='hartwork/gentoo-stage3-plus-gentoolkit')

    eclean_pkg_group = parser.add_argument_group('arguments forwarded to eclean')

    eclean_pkg_group.add_argument('--pretend',
                                  default=False,
                                  action='store_true',
                                  help='only display what would be cleaned '
                                  '(default: delete files)')
    eclean_pkg_group.add_argument('--time-limit',
                                  default='30d',
                                  metavar='DURATION',
                                  help='exclude files modified since DURATION from deletion'
                                  ' (default: "%(default)s")')

    return parser.parse_args(argv[1:])


def enrich_config(config):
    enrich_host_distdir_of(config)
    enrich_host_portdir_of(config)
    enrich_host_pkgdir_of(config)


def clean_packages(config):
    eclean_pkg_command = [
        'eclean-pkg',
        f'--time-limit={shlex.quote(config.time_limit)}',
    ]
    eclean_dist_command = [
        'eclean-dist',
        f'--time-limit={shlex.quote(config.time_limit)}',
    ]

    if config.interactive:
        eclean_dist_command.append('--interactive')
        eclean_pkg_command.append('--interactive')

    if config.pretend:
        eclean_dist_command.append('--pretend')
        eclean_pkg_command.append('--pretend')

    container_command_flat = ' && '.join(' '.join(shlex.quote(e) for e in argv)
                                         for argv in (eclean_pkg_command, eclean_dist_command))

    docker_run_args = [
        '--rm',
        '-v',
        f'{config.host_portdir}:/var/db/repos/gentoo:ro',
        '-v',
        f'{config.host_pkgdir}:/var/cache/binpkgs:rw',
        '-v',
        f'{config.host_distdir}:/var/cache/distfiles:rw',
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
        enrich_config(config)
        clean_packages(config)
