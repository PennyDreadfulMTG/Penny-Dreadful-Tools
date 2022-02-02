import json
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union

import humps
from flask import Response, current_app, request

from shared import configuration
from shared.container import Container
from shared.serialization import extra_serializer


def process_github_webhook() -> Response:
    if request.headers.get('X-GitHub-Event') == 'push':
        payload = json.loads(request.data)
        expected = 'refs/heads/{0}'.format(current_app.config['branch'])
        if payload['ref'] == expected:
            try:
                subprocess.check_output(['git', 'fetch'])
                subprocess.check_output(['git', 'reset', '--hard', 'origin/{0}'.format(current_app.config['branch'])])
                try:
                    subprocess.check_output([sys.executable, '-m', 'pipenv', 'install', '--system'])
                except subprocess.CalledProcessError:
                    pass
                try:
                    subprocess.check_output(['npm', 'run-script', 'build'])
                except subprocess.CalledProcessError:
                    pass
                # import uwsgi  # pylint: disable=import-outside-toplevel
                # uwsgi.reload()
                return return_json({'rebooting': False})
            except ImportError:
                pass
    return return_json({
        'rebooting': False,
        'commit-id': current_app.config['commit-id'],
        'current_branch': current_app.config['branch'],
        'ref': payload['ref'],
        'expected': expected,
    })

def commit_id() -> Response:
    return return_json(current_app.config['commit-id'])

def validate_api_key() -> Optional[Response]:
    if request.form.get('api_token', None) == configuration.get('pdbot_api_token'):
        return None
    return return_json(generate_error('UNAUTHORIZED', 'Invalid API key'), status=403)

def generate_error(code: str, msg: str, **more: Any) -> Dict[str, Any]:
    return {'error': True, 'code': code, 'msg': msg, **more}

def return_json(content: Union[bool, Dict[str, Any], None, List[Container], List[Dict[str, str]]], status: int = 200, camelize: bool = False) -> Response:
    s = json.dumps(content, default=extra_serializer)
    r = Response(response=s, status=status, mimetype='application/json')
    return r

def return_camelized_json(content: Dict[str, Any]) -> Response:
    content = humps.camelize(content)
    return return_json(content)
