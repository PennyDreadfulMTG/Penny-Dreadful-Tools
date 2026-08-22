import subprocess
from unittest import mock

from shared_web import fonts


def test_regenerate_symbols_font() -> None:
    with mock.patch.object(fonts.subprocess, 'Popen') as popen:
        fonts.regenerate_symbols_font()

    popen.assert_called_once_with(
        ['uv', 'run', '--frozen', 'python', 'run.py', 'maintenance', 'fonts'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
