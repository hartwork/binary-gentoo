# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import filecmp
import os
import sys
from argparse import ArgumentParser

from ..reporter import exception_reporting
from ..version import VERSION_STR


def report_new_and_changed_ebuilds(config):
    for root, dirs, files in os.walk(config.new_portdir):
        ebuild_files = [f for f in files if f.endswith('.ebuild')]
        if not ebuild_files:
            continue

        category_plus_package = os.path.relpath(root, config.new_portdir)
        package = category_plus_package.split(os.sep)[-1]

        for ebuild_file in ebuild_files:
            old_portdir_ebuild_file = os.path.join(config.old_portdir, category_plus_package,
                                                   ebuild_file)
            if os.path.exists(old_portdir_ebuild_file):
                new_portdir_ebuild_file = os.path.join(root, ebuild_file)
                if filecmp.cmp(old_portdir_ebuild_file, new_portdir_ebuild_file):
                    continue

            version = ebuild_file[len(package + '-'):-len('.ebuild')]
            category_plus_package_plus_version = f'{category_plus_package}-{version}'
            print(category_plus_package_plus_version)


def parse_command_line(argv):
    parser = ArgumentParser(
        prog='gentoo-tree-diff',
        description='Lists packages/versions/revisions that one portdir has over another')

    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION_STR}')

    parser.add_argument('old_portdir', metavar='OLD', help='location of old portdir')
    parser.add_argument('new_portdir', metavar='NEW', help='location of new portdir')

    config = parser.parse_args(argv[1:])

    config.old_portdir = os.path.realpath(config.old_portdir)
    config.new_portdir = os.path.realpath(config.new_portdir)

    return config


def main():
    with exception_reporting():
        config = parse_command_line(sys.argv)
        report_new_and_changed_ebuilds(config)


if __name__ == '__main__':
    main()
