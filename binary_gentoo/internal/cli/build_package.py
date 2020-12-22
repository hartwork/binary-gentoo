# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import datetime
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from argparse import ArgumentParser
from contextlib import suppress

from ..atoms import ATOM_LIKE_DISPLAY, extract_category_package_from
from ..reporter import announce_and_call, announce_and_check_output, exception_reporting
from ..version import VERSION_STR


def determine_host_gentoo_profile():
    output = announce_and_check_output(['eselect', 'profile', 'show'])
    return re.search('default/linux/[^ \\n]+', output).group(0)


def enrich_config(config):
    if config.gentoo_profile is None:
        config.gentoo_profile = determine_host_gentoo_profile()

    if config.host_distdir is None:
        config.host_distdir = announce_and_check_output(['portageq', 'distdir']).rstrip()
    config.host_distdir = os.path.realpath(config.host_distdir)

    if config.host_portdir is None:
        config.host_portdir = announce_and_check_output(
            ['portageq', 'get_repo_path', '/', 'gentoo']).rstrip()
    config.host_portdir = os.path.realpath(config.host_portdir)

    if config.host_pkgdir is None:
        config.host_pkgdir = announce_and_check_output(['portageq', 'pkgdir']).rstrip()
    config.host_pkgdir = os.path.realpath(config.host_pkgdir)

    config.host_logdir = os.path.realpath(config.host_logdir)
    config.host_etc_portage = os.path.realpath(config.host_etc_portage)
    if config.host_tweaks_dir is not None:
        config.host_tweaks_dir = os.path.realpath(config.host_tweaks_dir)

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
    parser = ArgumentParser(prog='gentoo-package-build',
                            description='Builds a Gentoo package with Docker isolation')

    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION_STR}')

    parser.add_argument('--non-interactive',
                        dest='interactive',
                        default=True,
                        action='store_false',
                        help='run in non-interactive mode without a TTY')

    parser.add_argument('--docker-image',
                        default='gentoo/stage3-amd64',
                        metavar='IMAGE',
                        help='use Docker image IMAGE (default: "%(default)s")')

    parser.add_argument(
        '--gentoo-profile',
        metavar='PROFILE',
        help='enforce Gentoo profile PROFILE'
        ' (e.g. "default/linux/amd64/17.1/developer", default: auto-detect using eselect)')

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

    parser.add_argument(
        '--portdir',
        dest='host_portdir',
        metavar='DIR',
        help=(
            'enforce specific location for PORTDIR'
            ' (e.g. "/var/db/repos/gentoo" or "/usr/portage", default: auto-detect using portageq)'
        ))
    parser.add_argument('--pkgdir',
                        dest='host_pkgdir',
                        metavar='DIR',
                        help='enforce specific location for PKGDIR'
                        ' (e.g. "/var/cache/binpkgs" or "/usr/portage/packages", '
                        'default: auto-detect using portageq)')
    parser.add_argument('--distdir',
                        dest='host_distdir',
                        metavar='DIR',
                        help='enforce specific location for DISTDIR'
                        ' (e.g. "/var/cache/distfiles" or "/usr/portage/distfiles", '
                        'default: auto-detect using portageq)')
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

    parser.add_argument('--tweaks',
                        dest='host_tweaks_dir',
                        metavar='DIR',
                        help='location of directory containing tweak files (e.g. package.use)')

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

    parser.add_argument('atom',
                        metavar='ATOM',
                        help=f'Package atom (format "{ATOM_LIKE_DISPLAY}")')

    return parser.parse_args(argv[1:])


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

    emerge = ['env'] + emerge_env + ['emerge'] + emerge_args
    emerge_quoted_flat = ' '.join(emerge)
    rebuild_or_not = f'--usepkg={"n" if config.enforce_rebuild else "y"}'
    install_or_not = '' if config.enforce_installation else '--buildpkgonly'

    container_profile_dir = os.path.join(container_portdir, 'profiles', config.gentoo_profile)
    container_command_shared_prefix = [
        f'ln -s {shlex.quote(container_portdir)} /var/db/repos/gentoo',
        'set -x',

        # This is to avoid access to potentially missing link /etc/portage/make.profile .
        # We cannot run "eselect profile set <profile>" because
        # that would create /etc/portage/make.profile rather than /etc/make.profile .
        f'ln -f -s {shlex.quote(container_profile_dir)} /etc/make.profile',
    ]

    container_command_flat_check = ' && '.join(container_command_shared_prefix + [
        f'{emerge_quoted_flat} --usepkg=y --onlydeps --pretend --verbose-conflicts {shlex.quote(config.atom)}',  # noqa: E501
    ])

    container_command_flat_build = ' && '.join(container_command_shared_prefix + [
        f'{emerge_quoted_flat} --usepkg=y --onlydeps {shlex.quote(config.atom)}',
        f'{emerge_quoted_flat} {rebuild_or_not} {install_or_not} {shlex.quote(config.atom)}',
    ])

    # Create pretend log dir
    category, package = extract_category_package_from(config.atom)
    host_pretend_logdir = os.path.join(config.host_logdir, 'pretend')
    host_pretend_logdir_category = os.path.join(host_pretend_logdir, category)
    host_pretend_logdir_category_package = os.path.join(host_pretend_logdir_category, package)
    os.makedirs(host_pretend_logdir_category_package, mode=0o700, exist_ok=True)

    with tempfile.TemporaryDirectory() as eventual_etc_portage:
        rsync_argv = [
            'rsync', '--archive', config.host_etc_portage + '/', eventual_etc_portage + '/'
        ]
        announce_and_call(rsync_argv)

        if config.host_tweaks_dir is not None:
            global_package_use_file = os.path.join(config.host_tweaks_dir, 'package.use')
            single_package_use_file = os.path.join(config.host_tweaks_dir, category, package,
                                                   'package.use')
            for package_use_file, target_basename in (
                (global_package_use_file, 'ZZ-global'),  # to be second last in alphabetic order
                (single_package_use_file,
                 f'ZZZ-{category}-{package}'),  # to be last in alphabetic order
            ):
                if os.path.exists(package_use_file):
                    target_package_use_file = os.path.join(eventual_etc_portage, 'package.use',
                                                           target_basename)
                    shutil.copyfile(package_use_file, target_package_use_file)

        filename_timestamp = str(datetime.datetime.now()).replace(' ', '-').replace(':',
                                                                                    '-').replace(
                                                                                        '.', '-')
        pretend_fail_log_filename = os.path.join(host_pretend_logdir_category_package,
                                                 filename_timestamp + '-fail.log')
        pretend_log_writer_process = subprocess.Popen(['tee', pretend_fail_log_filename],
                                                      stdin=subprocess.PIPE)
        try:
            for container_command_flat, stdout, remove_log_file in (
                (container_command_flat_check, pretend_log_writer_process.stdin, True),
                (container_command_flat_build, None, False),
            ):
                docker_run_args = [
                    '--rm',
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

                announce_and_call(['docker', 'run'] + docker_run_args, stdout=stdout)

                if remove_log_file:
                    os.remove(pretend_fail_log_filename)
                    with suppress(OSError):
                        os.rmdir(host_pretend_logdir_category_package)
                        os.rmdir(host_pretend_logdir_category)
        finally:
            pretend_log_writer_process.stdin.close()
            pretend_log_writer_process.wait()


def main():
    with exception_reporting():
        config = parse_command_line(sys.argv)
        enrich_config(config)
        build(config)


if __name__ == '__main__':
    main()
