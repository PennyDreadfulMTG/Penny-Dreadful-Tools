from shared import configuration
from shared_web.flask_app import PDFlask
from github_webhook import Webhook

from . import webhooks

APP = PDFlask(__name__)
WEBHOOK = Webhook(APP, endpoint='/api/github')

@APP.route('/')
def home():
    return 'build-commit-id: ' + APP.config['commit-id']

@WEBHOOK.hook()
def on_push(data):
    print('Got push')
    return data

@WEBHOOK.hook(event_type='status')
def on_status(data):
    sha = data.get('sha')
    context = data.get('context')
    state = data.get('state')
    print(f'Got status for {sha}: {context} = {state}')
    if context == webhooks.PDM_CHECK_CONTEXT:
        return 'Ignoring own status'
    pr = webhooks.get_pr_from_status(data)
    if pr is None:
        resp = 'Commit is no longer HEAD.  Ignoring'
        print(resp)
        return resp
    print(f'Commit belongs to {pr.number}')
    webhooks.check_pr_for_mergability(pr)
    return data

@WEBHOOK.hook(event_type='check_suite')
def on_check_suite(data):
    print('Got check_suite')
    return data

@WEBHOOK.hook(event_type='pull_request')
def on_pull_request(data):
    org, repo, pr_number = webhooks.parse_pr_url(data['pull_request']['url'])
    print([org, repo, pr_number])
    if data['action'] == 'synchronize' or data['action'] == 'opened':
        webhooks.set_check(data, 'pending', 'Waiting for tests')
    if data['action'] == 'labeled':
        pr = webhooks.load_pr(data)
        return webhooks.check_pr_for_mergability(pr)
