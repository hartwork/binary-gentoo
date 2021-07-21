# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os
import re
import sys
from argparse import ArgumentParser
from contextlib import suppress
from dataclasses import dataclass
from unittest.mock import Mock

from ..reporter import exception_reporting
from ._enrich import enrich_host_pkgdir_of
from ._parser import add_pkgdir_argument_to, add_version_argument_to


@dataclass
class BinaryPackage:
    full_name: str
    build_id: int
    cpv: str
    path: str

    def __str__(self):
        return self.full_name


def parse_package_block(package_block: str) -> BinaryPackage:
    d = {}
    for line in package_block.split('\n'):
        if not line:
            continue
        key, value = line.split(': ', maxsplit=1)
        d[key] = value

    return BinaryPackage(
        full_name=f'{d["CPV"]}-{d["BUILD_ID"]}',
        build_id=d['BUILD_ID'],
        cpv=d['CPV'],
        path=d.get('PATH', f'{d["CPV"]}.tbz2'),  # for FEATURES=-binpkg-multi-instance
    )


def has_safe_package_path(package):
    return (not package.path.startswith('/') and '..' not in package.path
            and 2 <= len(package.path.split('/')) <= 3)


def run(config):
    packages_index_filename = os.path.join(config.host_pkgdir, 'Packages')

    with open(packages_index_filename) as f:
        content = f.read()
    blocks = content.split('\n\n')
    header, *packages_blocks = blocks

    matcher = (re.compile(config.metadata, flags=re.MULTILINE) if config.metadata else Mock(
        search=Mock(return_value=True)))
    packages_to_keep = []
    packages_to_delete = []

    for package_block in packages_blocks:
        target = packages_to_delete if (package_block
                                        and matcher.search(package_block)) else packages_to_keep
        target.append(package_block)

    for package_block in packages_to_delete:
        package = parse_package_block(package_block)
        if has_safe_package_path(package):
            print(f'Dropping entry {package.full_name!r} and deleting file {package.path!r}...')
            if not config.pretend:
                abs_path_package_file = os.path.join(config.host_pkgdir, package.path)
                with suppress(FileNotFoundError):
                    os.remove(abs_path_package_file)
                    with suppress(OSError):
                        abs_path_package_dir = os.path.dirname(abs_path_package_file)
                        os.rmdir(abs_path_package_dir)
                        abs_path_category_dir = os.path.dirname(abs_path_package_dir)
                        os.rmdir(abs_path_category_dir)
        else:
            print(f'Dropping entry {package.full_name!r} BUT SKIPPING file {package.path!r}...')

    if not config.pretend:
        with open(packages_index_filename, 'w') as f:
            content = '\n\n'.join([header] + packages_to_keep)
            f.write(content)

    print(f'{len(packages_to_delete)} of {len(packages_blocks)} package(s) dropped')


def parse_command_line(argv):
    parser = ArgumentParser(prog='gentoo-packages',
                            description='Do operations on pkgdir'
                            ' (other than "emaint --fix binhost")')

    add_version_argument_to(parser)
    add_pkgdir_argument_to(parser)

    parser.add_argument('--metadata',
                        metavar='REGEX',
                        help='limit operation to all packages '
                        'where any metadata line matches '
                        'pattern REGEX (e.g. "CPV: virtual/.+")')
    parser.add_argument('--pretend',
                        default=False,
                        action='store_true',
                        help='only display what would be cleaned '
                        '(default: delete files)')

    commands_group = parser.add_argument_group('commands')
    commands_group.add_argument('--delete',
                                action='store_true',
                                required='True',
                                help='drop package entries and '
                                'delete their respective .xpak/.tbz2 files')

    return parser.parse_args(argv[1:])


def enrich_config(config):
    enrich_host_pkgdir_of(config)


def main():
    with exception_reporting():
        config = parse_command_line(sys.argv)
        enrich_config(config)
        run(config)


if __name__ == '__main__':
    main()
