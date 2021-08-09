# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

import shlex
import signal
import subprocess
import sys
from contextlib import contextmanager
from subprocess import CalledProcessError
from unittest.mock import patch


def _announce_command(argv):
    print('# ' + ' '.join(shlex.quote(a) for a in argv))


def announce_and_call(argv, stdout=None):
    _announce_command(argv)
    subprocess.check_call(argv, stdout=stdout)


def announce_and_check_output(argv):
    _announce_command(argv)
    return subprocess.check_output(argv).decode('utf-8')


class _ReadableCalledProcessError(CalledProcessError):
    def __str__(self):
        flat_quoted_cmd = ' '.join(shlex.quote(s) for s in self.cmd)
        with patch.object(self, 'cmd', 'X'):
            res = super().__str__().replace("Command 'X'", f'Command "{flat_quoted_cmd}"')
        return res


@contextmanager
def _readable_called_process_errors():
    try:
        yield
    except CalledProcessError as e:
        raise _ReadableCalledProcessError(e.returncode, e.cmd, e.output, e.stderr)


@contextmanager
def exception_reporting():
    try:
        with _readable_called_process_errors():
            yield
    except KeyboardInterrupt:
        sys.exit(128 + signal.SIGINT)
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)
