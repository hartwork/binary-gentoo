# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import re

_cp_pattern = '(?P<category>[a-z0-9-_]+)/(?P<package>[a-zA-Z0-9+-]+)'
_v_pattern = r'(?P<version>[0-9]+(\.[0-9]+[a-z]?)*(_(alpha|beta|pre|rc|p)[0-9]*)*)(?P<revision>-r[0-9]+)?'  # noqa: E501
_cpv_pattern = f'{_cp_pattern}-{_v_pattern}'
_atom_cpv_pattern = f'={_cp_pattern}-{_v_pattern}'
_set_pattern = '(?P<set>@[a-z0-9-_]+)'

ATOM_LIKE_DISPLAY = '[=]<category>/<package>[-<version>[-r<revision>]]'


def extract_category_package_from(atomlike):
    # first check for regular category and package names
    for pattern in (_cp_pattern, _cpv_pattern, _atom_cpv_pattern):
        match = re.compile(pattern).match(atomlike)
        if match is not None:
            break
    else:
        # if not found, see if we have a set
        match = re.compile(_set_pattern).match(atomlike)
        if match is None:
            # if still not found, raise an error
            raise ValueError(f'Not valid "{ATOM_LIKE_DISPLAY}" syntax: {atomlike!r}')
        else:
            return 'set', match.group('set')
    return match.group('category'), match.group('package')
