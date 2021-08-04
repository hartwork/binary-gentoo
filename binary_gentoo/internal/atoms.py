# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import re

_cp_pattern = '(?P<category>[a-z0-9-_]+)/(?P<package>[a-zA-Z0-9+-]+)'
_v_pattern = r'(?P<version>[0-9]+(\.[0-9]+[a-z]?)*(_(alpha|beta|pre|rc|p)[0-9]*)*)(?P<revision>-r[0-9]+)?'  # noqa: E501
_cpv_pattern = f'{_cp_pattern}-{_v_pattern}'
_atom_cpv_pattern = f'={_cp_pattern}-{_v_pattern}'
_set_pattern = '(?P<set>@[a-z0-9-_]+)'

ATOM_LIKE_DISPLAY = '[=]<category>/<package>[-<version>[-r<revision>]]'
SET_DISPLAY = '@<set>'


def extract_category_package_from(atomlike):
    for pattern in (_atom_cpv_pattern, _cpv_pattern, _cp_pattern):
        match = re.compile(pattern).match(atomlike)
        if match is not None:
            break
    else:
        raise ValueError(f'Not valid "{ATOM_LIKE_DISPLAY}" syntax: {atomlike!r}')
    return match.group('category'), match.group('package')


def extract_set_from(set_candidate):
    match = re.compile(_set_pattern).match(set_candidate)
    if match is None:
        raise ValueError(f'Not valid "{SET_DISPLAY}" syntax: {set_candidate!r}')
    return match.group('set')
