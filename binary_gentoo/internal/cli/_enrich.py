# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import os

from ..reporter import announce_and_check_output


def enrich_host_pkgdir_of(config):
    if config.host_pkgdir is None:
        config.host_pkgdir = announce_and_check_output(['portageq', 'pkgdir']).rstrip()
    config.host_pkgdir = os.path.realpath(config.host_pkgdir)


def enrich_host_portdir_of(config):
    if config.host_portdir is None:
        config.host_portdir = announce_and_check_output(
            ['portageq', 'get_repo_path', '/', 'gentoo']).rstrip()
    config.host_portdir = os.path.realpath(config.host_portdir)


def enrich_host_distdir_of(config):
    if config.host_distdir is None:
        config.host_distdir = announce_and_check_output(['portageq', 'distdir']).rstrip()
    config.host_distdir = os.path.realpath(config.host_distdir)
