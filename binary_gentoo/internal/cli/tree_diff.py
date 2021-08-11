# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import filecmp
import os
import re
import sys
from argparse import ArgumentParser
from typing import Set

from ..reporter import announce_and_check_output, exception_reporting
from ._parser import add_version_argument_to

_keywords_pattern = re.compile('KEYWORDS="(?P<keywords>[^"]*)"')
_filename_9999_pattern = re.compile(r'9999(-r[0-9]+)?\.ebuild$')


def _replace_special_keywords_for_ebuild(accept_keywords: Set[str],
                                         ebuild_keywords: Set[str]) -> Set[str]:
    effective_keywords = set(accept_keywords)
    if '**' in effective_keywords:
        effective_keywords.remove('**')
        effective_keywords |= ebuild_keywords
    if '*' in effective_keywords:
        effective_keywords.remove('*')
        effective_keywords |= {kw for kw in ebuild_keywords if not kw.startswith('~')}
    if '~*' in effective_keywords:
        effective_keywords.remove('~*')
        effective_keywords |= {kw for kw in ebuild_keywords if kw.startswith('~')}
    return effective_keywords


def _get_relevant_keywords_set_for(ebuild_filepath: str, accept_keywords: Set[str]) -> Set[str]:
    with open(ebuild_filepath) as ifile:
        ebuild_content = ifile.read()

    match = _keywords_pattern.search(ebuild_content)
    if match is None:
        ebuild_keywords = set()
    else:
        ebuild_keywords = match.group('keywords')
        ebuild_keywords = {kw for kw in ebuild_keywords.split(" ") if kw}

    accept_keywords = _replace_special_keywords_for_ebuild(accept_keywords, ebuild_keywords)

    return set(accept_keywords) & set(ebuild_keywords)


def iterate_new_and_changed_ebuilds(config):
    for root, dirs, files in os.walk(config.new_portdir):
        ebuild_files = [f for f in files if f.endswith('.ebuild')]
        if not ebuild_files:
            continue

        category_plus_package = os.path.relpath(root, config.new_portdir)
        package = category_plus_package.split(os.sep)[-1]

        for ebuild_file in ebuild_files:
            old_portdir_ebuild_filepath = os.path.join(config.old_portdir, category_plus_package,
                                                       ebuild_file)
            new_portdir_ebuild_filepath = os.path.join(root, ebuild_file)

            # don't output 9999 ebuilds
            if re.search(_filename_9999_pattern, ebuild_file) is not None:
                continue

            # don't output if files are identical
            # old_portdir_ebuild_filepath_exists = os.path.exists(old_portdir_ebuild_filepath)
            # if old_portdir_ebuild_filepath_exists:
            if os.path.exists(old_portdir_ebuild_filepath):
                if filecmp.cmp(old_portdir_ebuild_filepath, new_portdir_ebuild_filepath):
                    continue

            # don't output if the new ebuild doesn't contain the accept keywords
            new_ebuild_relevant_keywords = _get_relevant_keywords_set_for(
                new_portdir_ebuild_filepath, config.keywords)
            if not new_ebuild_relevant_keywords:
                continue

            # don't output if both old and new file include the same keywords
            # unless the user has asked for all changes
            # (i.e., when unrelated keywords or other parts of the ebuild have changed)
            # if not config.pessimistic and old_portdir_ebuild_filepath_exists:
            if not config.pessimistic and os.path.exists(old_portdir_ebuild_filepath):
                old_ebuild_relevant_keywords = _get_relevant_keywords_set_for(
                    old_portdir_ebuild_filepath, config.keywords)
                if new_ebuild_relevant_keywords == old_ebuild_relevant_keywords:
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

    parser.add_argument('--pessimistic',
                        default=False,
                        action='store_true',
                        help='be more robust towards missing revbumps by including ebuilds '
                        'that had non-keyword content changes (default: only include previously '
                        'existing ebuilds when relevant keywords have been added)')

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
