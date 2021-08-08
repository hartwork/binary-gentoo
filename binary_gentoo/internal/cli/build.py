# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import base64
import datetime
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from argparse import ArgumentParser
from contextlib import suppress
from enum import Enum, auto

import yaml

from ..atoms import ATOM_LIKE_DISPLAY, SET_DISPLAY, extract_category_package_from, extract_set_from
from ..reporter import announce_and_call, announce_and_check_output, exception_reporting
from ._enrich import enrich_host_distdir_of, enrich_host_pkgdir_of, enrich_host_portdir_of
from ._parser import (add_distdir_argument_to, add_docker_image_argument_to,
                      add_interactive_argument_to, add_pkgdir_argument_to, add_portdir_argument_to,
                      add_version_argument_to)


class EmergeTargetType(Enum):
    PACKAGE = auto()
    SET = auto()


def determine_host_gentoo_profile():
    output = announce_and_check_output(['eselect', 'profile', 'show'])
    return re.search('default/linux/[^ \\n]+', output).group(0)


def enrich_config(config):
    if config.gentoo_profile is None:
        config.gentoo_profile = determine_host_gentoo_profile()

    enrich_host_distdir_of(config)
    enrich_host_portdir_of(config)
    enrich_host_pkgdir_of(config)

    config.host_logdir = os.path.realpath(config.host_logdir)
    config.host_etc_portage = os.path.realpath(config.host_etc_portage)
    if config.host_flavors_dir is not None:
        config.host_flavors_dir = os.path.realpath(config.host_flavors_dir)

    if config.cflags is None:
        config.cflags = announce_and_check_output(['portageq', 'envvar', 'CFLAGS']).rstrip()

    if config.cxxflags is None:
        config.cxxflags = announce_and_check_output(['portageq', 'envvar', 'CXXFLAGS']).rstrip()

    if config.ldflags is None:
        config.ldflags = announce_and_check_output(['portageq', 'envvar', 'LDFLAGS']).rstrip()

    if config.cpu_flags_x86 is None:
        config.cpu_flags_x86 = announce_and_check_output(['portageq', 'envvar',
                                                          'CPU_FLAGS_X86']).rstrip()

    return config


def parse_command_line(argv):
    parser = ArgumentParser(prog='gentoo-build',
                            description='Builds a Gentoo package with Docker isolation')

    add_version_argument_to(parser)

    add_interactive_argument_to(parser)

    add_docker_image_argument_to(parser)

    parser.add_argument(
        '--gentoo-profile',
        metavar='PROFILE',
        help='enforce Gentoo profile PROFILE'
        ' (e.g. "default/linux/amd64/17.1/developer", default: auto-detect using eselect)')

    parser.add_argument('--use', help='custom one-off use flags (default: none)')

    parser.add_argument('--makeopts',
                        metavar='MAKEOPTS',
                        default='-j1',
                        help='enforce custom MAKEOPTS (default: "%(default)s")')
    parser.add_argument('--cflags',
                        metavar='CFLAGS',
                        help='enforce custom CFLAGS (default: auto-detect using portageq)')
    parser.add_argument('--cxxflags',
                        metavar='CXXFLAGS',
                        help='enforce custom CXXFLAGS (default: auto-detect using portageq)')
    parser.add_argument('--ldflags',
                        metavar='LDFLAGS',
                        help='enforce custom LDFLAGS (default: auto-detect using portageq)')
    parser.add_argument(
        '--cpu-flags-x86',
        metavar='FLAGS',
        help=
        'enforce custom CPU_FLAGS_X86 (default: auto-detect using portageq (not cpuid2cpuflags))')

    add_portdir_argument_to(parser)
    add_pkgdir_argument_to(parser)
    add_distdir_argument_to(parser)

    parser.add_argument(
        '--logdir',
        dest='host_logdir',
        metavar='DIR',
        default=os.path.expanduser('~/.local/var/log/portage'),
        help='enforce specific location for PORTAGE_LOGDIR (default: "%(default)s")')
    parser.add_argument('--etc-portage',
                        dest='host_etc_portage',
                        metavar='DIR',
                        default='/etc/portage',
                        help='enforce specific location for /etc/portage (default: "%(default)s")')

    parser_group_flavors_or_image = parser.add_mutually_exclusive_group()

    parser_group_flavors_or_image.add_argument(
        '--flavors',
        dest='host_flavors_dir',
        metavar='DIR',
        help=('location of directory containing '
              'sparse <category>/<package>/flavors.yml file hierarchy'))

    parser.add_argument('--shy-rebuild',
                        dest='enforce_rebuild',
                        default=True,
                        action='store_false',
                        help='do not enforce a rebuild (default: always rebuild)')
    parser.add_argument('--install',
                        dest='enforce_installation',
                        default=False,
                        action='store_true',
                        help='enforce installation (default: build but do not install)')

    parser.add_argument('--update',
                        default=False,
                        action='store_true',
                        help='pass --update to emerge (default: execute emerge without --update)')

    parser_group_flavors_or_image.add_argument(
        '--tag-docker-image',
        metavar='IMAGE',
        dest='tag_docker_image',
        help='create a Docker image from the resulting container')

    parser.add_argument(
        'emerge_target',
        metavar='CP|CPV|=CPV|@SET',
        help=f'Package atom or set (format "{ATOM_LIKE_DISPLAY}" or "{SET_DISPLAY}")')

    return parser.parse_args(argv[1:])


def classify_emerge_target(emerge_target):
    try:
        emerge_target_type = EmergeTargetType.PACKAGE
        category, package_or_set = extract_category_package_from(emerge_target)
    except ValueError as package_error:
        try:
            emerge_target_type = EmergeTargetType.SET
            category, package_or_set = 'sets', extract_set_from(emerge_target)
        except ValueError as set_error:
            raise ValueError(f'{package_error}; {set_error}')

    return emerge_target_type, category, package_or_set


def build(config):
    cpu_threads_to_use = max(1, len(os.sched_getaffinity(0)) + 1)
    container_portdir = '/usr/portage'
    container_logdir = '/var/log/portage/'

    emerge_args = [
        '--oneshot',
        '--verbose',
        '--tree',
        '--jobs=2',
        f'--load-average={cpu_threads_to_use}',
        '--buildpkg=y',
        '--keep-going',
        '--with-bdeps=y',
        '--complete-graph',
    ]
    if config.update:
        emerge_args += [
            '--update',
            '--changed-use',
            '--newuse',
            '--deep',
        ]

    features_flat = ' '.join([
        '-news',
        'binpkg-multi-instance',
        'split-elog',
        'split-log',

        # Because we are in container, from https://bugs.gentoo.org/680456#c3
        '-ipc-sandbox',
        '-mount-sandbox',
        '-network-sandbox',
        '-pid-sandbox',
        '-sandbox',
        '-usersandbox',
    ])
    emerge_env = [
        'EMERGE_DEFAULT_OPTS=',  # so that we win over /etc/portage/make.conf
        f'FEATURES={shlex.quote(features_flat)}',
        f'PORTDIR={shlex.quote(container_portdir)}',
        'PORTAGE_ELOG_SYSTEM=save',  # i.e. enforce that log are written to disk
        'PORTAGE_ELOG_CLASSES=',  # i.e. nothing but build logs
        f'PORTAGE_LOGDIR={shlex.quote(container_logdir)}',
        f'MAKEOPTS={shlex.quote(config.makeopts)}',
        f'CPU_FLAGS_X86={shlex.quote(config.cpu_flags_x86)}',
        f'CFLAGS={shlex.quote(config.cflags)}',
        f'CXXFLAGS={shlex.quote(config.cxxflags)}',
        f'LDFLAGS={shlex.quote(config.ldflags)}',
    ]

    if config.use is not None:
        emerge_env.append(f'USE={shlex.quote(config.use)}')

    if config.tag_docker_image is not None:
        container_name = f'binary-gentoo-{uuid.uuid4().hex}'
    else:
        container_name = None

    emerge = ['env'] + emerge_env + ['emerge'] + emerge_args
    emerge_quoted_flat = ' '.join(emerge)
    rebuild_or_not = f'--usepkg={"n" if config.enforce_rebuild else "y"}'

    container_profile_dir = os.path.join(container_portdir, 'profiles', config.gentoo_profile)
    container_portdir_dir_link_target = '/var/db/repos/gentoo'
    container_make_profile = '/etc/make.profile'
    container_command_shared_prefix = [
        f'ln -s {shlex.quote(container_portdir)} {shlex.quote(container_portdir_dir_link_target)}',
        'set -x',

        # This is to avoid access to potentially missing link /etc/portage/make.profile .
        # We cannot run "eselect profile set <profile>" because
        # that would create /etc/portage/make.profile rather than /etc/make.profile .
        f'ln -f -s {shlex.quote(container_profile_dir)} {shlex.quote(container_make_profile)}',  # noqa: E501
    ]

    # Create log dir
    emerge_target_type, category, package_or_set = classify_emerge_target(config.emerge_target)
    host_logdir__root = os.path.join(config.host_logdir, 'binary-gentoo')
    host_logdir__category = os.path.join(host_logdir__root, category)
    host_logdir__category__package = os.path.join(host_logdir__category, package_or_set)
    os.makedirs(host_logdir__category__package, mode=0o700, exist_ok=True)

    with tempfile.TemporaryDirectory() as eventual_etc_portage:
        rsync_argv = [
            'rsync', '--archive', config.host_etc_portage + '/', eventual_etc_portage + '/'
        ]
        announce_and_call(rsync_argv)

        os.makedirs(os.path.join(eventual_etc_portage, 'package.use'), exist_ok=True)

        # Write package.use level "global", 1 of 4
        flavors_yml_doc = {}
        if config.host_flavors_dir is not None:
            global_package_use_file_source = os.path.join(config.host_flavors_dir, 'package.use')
            if os.path.exists(global_package_use_file_source):
                global_package_use_file_target = os.path.join(
                    eventual_etc_portage, 'package.use',
                    'ZZ-global')  # to be third last in alphabetic order
                shutil.copyfile(global_package_use_file_source, global_package_use_file_target)

            if emerge_target_type == EmergeTargetType.PACKAGE:
                flavors_yml_file = os.path.join(config.host_flavors_dir, category, package_or_set,
                                                'flavors.yml')
                with suppress(OSError), open(flavors_yml_file) as f:
                    # TODO validate flavors.yml file content
                    flavors_yml_doc = yaml.safe_load(f)

        # Write package.use level "common to all flavors", 2 of 4
        common_package_use_file_content = flavors_yml_doc.get('package.use')
        if common_package_use_file_content:
            common_package_use_file_target = os.path.join(
                eventual_etc_portage, 'package.use',
                'ZZZ-common')  # to be second last in alphabetic order
            with open(common_package_use_file_target, 'w') as f:
                print(common_package_use_file_content, file=f)

        # Build flavors
        for flavor in flavors_yml_doc.get('flavors', [{}]):

            # Write package.use level "single flavor", 3 of 4
            # NOTE: We're overwriting every time to not have package.use of the previous flavor
            #       affect the current build
            single_package_use_file_target = os.path.join(
                eventual_etc_portage, 'package.use',
                'ZZZZ-flavor')  # to be last in alphabetic order
            with open(single_package_use_file_target, 'w') as f:
                print(flavor.get('package.use', ''), file=f)

            filename_timestamp = str(datetime.datetime.now()).replace(' ', '-').replace(
                ':', '-').replace('.', '-')
            host_log_filename = os.path.join(host_logdir__category__package,
                                             filename_timestamp + '-fail.log')
            log_writer_process = subprocess.Popen(['tee', host_log_filename],
                                                  stdin=subprocess.PIPE)

            # Assemble build command list
            steps = flavor.get('steps', [{}])
            step_commands = container_command_shared_prefix
            prior_step_package_use_file_exists = False
            for step_index, step in enumerate(steps):
                is_last_step = step_index == len(steps) - 1

                # Re-write step-specific package.use file, 4 of 4
                package_use_content = base64.encodebytes(
                    step.get('package.use', '').encode('ascii')).decode("ascii").replace('\n', '')
                flavor_package_use_file = '/etc/portage/package.use/ZZZZZ-step'  # to be very last
                if package_use_content:
                    step_commands.append(
                        f'base64 -d <<<{package_use_content!r} | tee {flavor_package_use_file}')
                    prior_step_package_use_file_exists = True
                elif prior_step_package_use_file_exists:
                    step_commands.append(f'rm -f {flavor_package_use_file}')  # from previous step
                    prior_step_package_use_file_exists = False

                enforce_installation = config.enforce_installation or not is_last_step or (
                    config.tag_docker_image is not None)
                install_or_not = '' if enforce_installation else '--buildpkgonly'
                if not config.update:
                    step_commands.append(
                        f'{emerge_quoted_flat} --usepkg=y --onlydeps --verbose-conflicts {shlex.quote(config.emerge_target)}'  # noqa: E501
                    )
                step_commands.append(
                    f'{emerge_quoted_flat} {rebuild_or_not} {install_or_not} {shlex.quote(config.emerge_target)}'  # noqa: E501
                )

            if container_name is not None:
                # Cleanup symlinks that were created in previous steps, otherwise subsequent
                # builds with --tag-docker-image will fail when the same symlinks are re-created
                step_commands += [
                    f'rm {shlex.quote(container_portdir_dir_link_target)}',
                    f'rm {shlex.quote(container_make_profile)}',
                ]

            container_command_flat = ' && '.join(step_commands)

            if config.tag_docker_image is not None:
                docker_container_lifecycle_arg = f'--name={container_name}'
            else:
                docker_container_lifecycle_arg = '--rm'

            docker_run_args = [
                docker_container_lifecycle_arg,
                '-v',
                f'{eventual_etc_portage}:/etc/portage:rw',
                '-v',
                f'{config.host_logdir}:{container_logdir}:rw',
                '-v',
                f'{config.host_portdir}:{container_portdir}:ro',
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

            try:
                announce_and_call(['docker', 'run'] + docker_run_args,
                                  stdout=log_writer_process.stdin)
                with suppress(FileNotFoundError):
                    os.remove(host_log_filename)
                with suppress(OSError):
                    os.rmdir(host_logdir__category__package)
                    os.rmdir(host_logdir__category)

                if config.tag_docker_image is not None:
                    announce_and_call(
                        ['docker', 'commit', container_name, config.tag_docker_image])
            finally:
                log_writer_process.stdin.close()
                log_writer_process.wait()

                if config.tag_docker_image is not None:
                    announce_and_call(['docker', 'rm', container_name])


def main():
    with exception_reporting():
        config = parse_command_line(sys.argv)
        enrich_config(config)
        build(config)
