# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import json


def dump_json_for_humans(obj, fp):
    """Wrapper around ``json.dump`` with custom config"""
    json.dump(obj, fp, indent='  ', sort_keys='True')
    print(file=fp)  # i.e. trailing newline
