import subprocess
import sys
from unittest import mock

from flask import Flask

from shared_web import api


def test_push_deployment_rebuilds_symbols_font() -> None:
    app = Flask(__name__)
    app.config['branch'] = 'master'

    with (
        app.test_request_context('/api/gitpull', method='POST', headers={'X-GitHub-Event': 'push'}, json={'ref': 'refs/heads/master'}),
        mock.patch.object(api.subprocess, 'check_output') as check_output,
        mock.patch.object(api.subprocess, 'Popen') as popen,
    ):
        response = api.process_github_webhook()

    assert response.status_code == 200
    assert check_output.call_args_list == [
        mock.call(['git', 'fetch']),
        mock.call(['git', 'reset', '--hard', 'origin/master']),
        mock.call([sys.executable, '-m', 'uv', 'sync', '--frozen']),
        mock.call(['npm', 'run-script', 'build']),
    ]
    popen.assert_called_once_with(
        ['uv', 'run', '--frozen', 'python', 'run.py', 'maintenance', 'fonts'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
