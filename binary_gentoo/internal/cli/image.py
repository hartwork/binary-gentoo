import sys
import uuid
from argparse import ArgumentParser

from .build import build, enrich_config, add_build_arguments_to
from ..reporter import exception_reporting, announce_and_call


def parse_command_line(argv):
    parser = ArgumentParser(prog='gentoo-image',
                            description='Creates a Gentoo image with Docker isolation')

    parser = add_build_arguments_to(parser)

    parser.add_argument('--tag',
                        dest='tag',
                        default='gentoo-build-host',
                        help='tag of the new image (default: gentoo-build-host)')

    return parser.parse_args(argv[1:])


def create_image(config):
    config.enforce_installation = True
    container_name = f'gentoo-build-host-{uuid.uuid4().hex}'
    build(config, container_name)

    announce_and_call(['docker', 'commit', container_name, config.tag])
    announce_and_call(['docker', 'rm', container_name])


def main():
    with exception_reporting():
        config = parse_command_line(sys.argv)
        enrich_config(config)
        create_image(config)


if __name__ == '__main__':
    main()
