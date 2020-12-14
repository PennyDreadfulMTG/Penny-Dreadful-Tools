from typing import Any, Dict, Union

from flask import redirect
from github_webhook import Webhook
from werkzeug import wrappers

from shared_web.flask_app import PDFlask

from . import webhooks

APP = PDFlask(__name__)
WEBHOOK = Webhook(APP, endpoint='/api/github')

@APP.route('/')
def home() -> str:
    return 'build-commit-id: ' + APP.config['commit-id']

@WEBHOOK.hook()
def on_push(data: Dict[str, Any]) -> Dict[str, Any]:
    ref = data['ref']
    print(f'Got push on {ref}')
    return data

@WEBHOOK.hook(event_type='status')
def on_status(data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
    sha = data.get('sha')
    context = data.get('context')
    state = data.get('state')
    print(f'Got status for {sha}: {context} = {state}')
    if context == webhooks.PDM_CHECK_CONTEXT:
        return 'Ignoring own status'
    pr = webhooks.get_pr_from_status(data)
    if pr is None:
        return 'Commit is no longer HEAD.  Ignoring'
    print(f'Commit belongs to {pr.number}')
    webhooks.check_pr_for_mergability(pr)
    return data

@WEBHOOK.hook(event_type='check_suite')
def on_check_suite(data: Dict[str, Any]) -> Dict[str, Any]:
    print('Got check_suite')
    return data

@WEBHOOK.hook(event_type='pull_request')
def on_pull_request(data: Dict[str, Any]) -> str:
    org, repo, pr_number = webhooks.parse_pr_url(data['pull_request']['url'])
    print([org, repo, pr_number])
    if data['action'] == 'synchronize' or data['action'] == 'opened':
        webhooks.set_check(data, 'pending', 'Waiting for tests')
    if data['action'] == 'labeled' or data['action'] == 'unlabeled':
        pr = webhooks.load_pr(data)
        if pr.state == 'open':
            return webhooks.check_pr_for_mergability(pr)
        if pr.state == 'closed' and 'Overdue-on-GH' in [l.name for l in pr.as_issue().labels]:
            # We can't actually reboot when `master` is pushed like the other sites.
            # So this is a lovely hack to reboot ourselves when we absolutely need to.
            try:
                import uwsgi  # pylint: disable=import-outside-toplevel
                uwsgi.reload()
            except ImportError:
                pass
            return 'I need to be reloaded'
    return ''

@APP.route('/cards/<path:name>/')
def card(name: str) -> wrappers.Response:
    return redirect('https://pennydreadfulmagic.com/cards/{name}/'.format(name=name))
