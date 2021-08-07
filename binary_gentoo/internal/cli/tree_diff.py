# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import filecmp
import os
import re
import sys
from argparse import ArgumentParser
from typing import Iterable, Set

from ..reporter import announce_and_check_output, exception_reporting
from ._parser import add_version_argument_to

_keywords_pattern = re.compile('KEYWORDS="(?P<keywords>[^"]*)"')


def _get_relevant_keywords_set_for(ebuild_content: str,
                                   accept_keywords: Iterable[str]) -> Set[str]:
    match = _keywords_pattern.search(ebuild_content)
    if match is None:
        ebuild_keywords = []
    else:
        ebuild_keywords = match.group('keywords')
        ebuild_keywords = [kw for kw in ebuild_keywords.split(" ") if kw]

    # replace special keywords by the relevant keywords from the ebuild
    if '**' in accept_keywords:
        accept_keywords = ebuild_keywords
    elif '*' in accept_keywords:
        accept_keywords = [kw for kw in ebuild_keywords if not kw.startswith('~')]
    elif '~*' in accept_keywords:
        accept_keywords = [kw for kw in ebuild_keywords if kw.startswith('~')]

    return set(accept_keywords) & set(ebuild_keywords)


def _keywords_included_in_ebuild(accept_keywords: Iterable[str],
                                 new_portdir_ebuild_file: str,
                                 old_portdir_ebuild_file: str = None) -> bool:
    """
    Check if the new_portdir_ebuild_file contains the accept_keywords. Returns True if that is the
    case, otherwise False. If old_portdir_ebuild_file is passed, an extra comparison is made
    between the relevant keywords in the old and the new ebuild. If these keywords are identical,
    return False.
    """

    with open(new_portdir_ebuild_file) as ifile:
        new_ebuild_content = ifile.read()
    new_ebuild_relevant_keywords = _get_relevant_keywords_set_for(new_ebuild_content,
                                                                  accept_keywords)

    # return False if the new file doesn't include the specified keywords
    if not new_ebuild_relevant_keywords:
        return False

    if old_portdir_ebuild_file is not None and os.path.exists(old_portdir_ebuild_file):
        with open(old_portdir_ebuild_file) as ifile:
            old_ebuild_content = ifile.read()
        old_ebuild_relevant_keywords = _get_relevant_keywords_set_for(
            old_ebuild_content, accept_keywords)

        # return False if both old and new file include the same keywords
        # (i.e., when only other keywords have changed)
        if new_ebuild_relevant_keywords == old_ebuild_relevant_keywords:
            return False

    # in all other cases, return True
    return True


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

            # don't output 9999 ebuilds
            if ebuild_file.endswith('-9999.ebuild'):
                continue

            # don't output if files are identical
            if os.path.exists(old_portdir_ebuild_file):
                if filecmp.cmp(old_portdir_ebuild_file, new_portdir_ebuild_file):
                    continue

            # include only specific keywords sets
            if not _keywords_included_in_ebuild(
                    config.keywords, new_portdir_ebuild_file,
                    old_portdir_ebuild_file if not config.report_changes else None):
                continue

            version = ebuild_file[len(package + '-'):-len('.ebuild')]
            yield f'{category_plus_package}-{version}'


def report_new_and_changed_ebuilds(config):
    for cpv in iterate_new_and_changed_ebuilds(config):
        print(cpv)


def enrich_config(config):
    if config.keywords is None:
        config.keywords = announce_and_check_output(['portageq', 'envvar',
                                                     'ACCEPT_KEYWORDS']).rstrip()
    if not config.keywords:
        raise ValueError("At least one keyword must be specified")

    # add stable keywords for testing keywords
    config.keywords = {kw for kw in config.keywords.split(" ") if kw}
    config.keywords |= {k[1:] for k in config.keywords if k.startswith('~')}

    return config


def parse_command_line(argv):
    parser = ArgumentParser(
        prog='gentoo-tree-diff',
        description='Lists packages/versions/revisions that one portdir has over another')

    add_version_argument_to(parser)

    parser.add_argument('--keywords',
                        help='include only packages/versions/revisions that have these keywords; '
                        'in case of multiple keywords a space-separated list can be provided '
                        '(default: auto-detect using portageq)')

    parser.add_argument('--report-changes',
                        default=False,
                        action='store_true',
                        help='include all ebuilds that have changed between the old and the new '
                        'portdir and that contain the specified keywords (default: only '
                        'include changed ebuilds for which keywords have changed too)')

    parser.add_argument('old_portdir', metavar='OLD', help='location of old portdir')
    parser.add_argument('new_portdir', metavar='NEW', help='location of new portdir')

    config = parser.parse_args(argv[1:])

    config.old_portdir = os.path.realpath(config.old_portdir)
    config.new_portdir = os.path.realpath(config.new_portdir)

    return config


def main():
    with exception_reporting():
        config = parse_command_line(sys.argv)
        enrich_config(config)
        report_new_and_changed_ebuilds(config)
