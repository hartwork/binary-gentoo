# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import filecmp
import os
import re
import sys
from argparse import ArgumentParser

from ._parser import add_version_argument_to
from ..reporter import exception_reporting

keywords_pattern = re.compile('KEYWORDS="(?P<keywords>.*?)"')


def _get_relevant_keywords_set_for(ebuild_content, expected_keywords):
    try:
        ebuild_keywords = keywords_pattern.search(ebuild_content).group('keywords')
    except AttributeError:
        # if the KEYWORDS variable is not found in the ebuild, we will assume the ebuild needs to be listed
        ebuild_keywords = expected_keywords
    expected_keywords_set = set(expected_keywords.split(" "))
    ebuild_keywords_set = set(ebuild_keywords.split(" "))

    return expected_keywords_set & ebuild_keywords_set


def iterate_new_and_changed_ebuilds(config):
    for root, dirs, files in os.walk(config.new_portdir):
        ebuild_files = [f for f in files if f.endswith('.ebuild')]
        if not ebuild_files:
            continue

        category_plus_package = os.path.relpath(root, config.new_portdir)
        package = category_plus_package.split(os.sep)[-1]

        for ebuild_file in ebuild_files:
            old_portdir_ebuild_file = os.path.join(config.old_portdir, category_plus_package,
                                                   ebuild_file)
            new_portdir_ebuild_file = os.path.join(root, ebuild_file)

            # don't output if files are identical
            if os.path.exists(old_portdir_ebuild_file):
                if filecmp.cmp(old_portdir_ebuild_file, new_portdir_ebuild_file):
                    continue

            if config.keywords:
                with open(new_portdir_ebuild_file, "r") as ifile:
                    new_ebuild_content = ifile.read()
                new_ebuild_relevant_keywords = _get_relevant_keywords_set_for(new_ebuild_content, config.keywords)

                # don't output if the new file doesn't include the specified keywords
                if len(new_ebuild_relevant_keywords) == 0:
                    continue

                if os.path.exists(old_portdir_ebuild_file):
                    with open(old_portdir_ebuild_file, "r") as ifile:
                        old_ebuild_content = ifile.read()
                    old_ebuild_relevant_keywords = _get_relevant_keywords_set_for(old_ebuild_content, config.keywords)

                    # don't output if both old and new file include the same keywords
                    # (i.e., when only other keywords have changed)
                    if new_ebuild_relevant_keywords == old_ebuild_relevant_keywords:
                        continue

            version = ebuild_file[len(package + '-'):-len('.ebuild')]
            yield f'{category_plus_package}-{version}'


def report_new_and_changed_ebuilds(config):
    for cpv in iterate_new_and_changed_ebuilds(config):
        print(cpv)


def parse_command_line(argv):
    parser = ArgumentParser(
        prog='gentoo-tree-diff',
        description='Lists packages/versions/revisions that one portdir has over another')

    add_version_argument_to(parser)

    parser.add_argument('--keywords',
                        dest='keywords',
                        default='',
                        help='filter the list on these keywords; '
                             'in case of multiple keywords a space-separated list can be provided '
                             '(default: all keywords)')
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
