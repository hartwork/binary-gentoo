# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import fcntl
import os
from contextlib import contextmanager, suppress


@contextmanager
def file_based_interprocess_locking(lock_filename):
    with open(lock_filename, 'w') as lock:
        fcntl.lockf(lock, fcntl.LOCK_EX)  # may block
        try:
            yield
        finally:
            fcntl.lockf(lock, fcntl.LOCK_UN)

            with suppress(FileNotFoundError):
                os.remove(lock_filename)
