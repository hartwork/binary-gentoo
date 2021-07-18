# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from ..version import VERSION_STR


def add_version_argument_to(parser):
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION_STR}')


def add_interactive_argument_to(parser):
    parser.add_argument('--non-interactive',
                        dest='interactive',
                        default=True,
                        action='store_false',
                        help='run in non-interactive mode without a TTY')


def add_docker_image_argument_to(parser, default='gentoo/stage3'):
    parser.add_argument('--docker-image',
                        default=default,
                        metavar='IMAGE',
                        help='use Docker image IMAGE (default: "%(default)s")')


def add_portdir_argument_to(parser):
    parser.add_argument(
        '--portdir',
        dest='host_portdir',
        metavar='DIR',
        help=(
            'enforce specific location for PORTDIR'
            ' (e.g. "/var/db/repos/gentoo" or "/usr/portage", default: auto-detect using portageq)'
        ))


def add_distdir_argument_to(parser):
    parser.add_argument('--distdir',
                        dest='host_distdir',
                        metavar='DIR',
                        help='enforce specific location for DISTDIR'
                        ' (e.g. "/var/cache/distfiles" or "/usr/portage/distfiles", '
                        'default: auto-detect using portageq)')


def add_pkgdir_argument_to(parser):
    parser.add_argument('--pkgdir',
                        dest='host_pkgdir',
                        metavar='DIR',
                        help='enforce specific location for PKGDIR'
                        ' (e.g. "/var/cache/binpkgs" or "/usr/portage/packages", '
                        'default: auto-detect using portageq)')
