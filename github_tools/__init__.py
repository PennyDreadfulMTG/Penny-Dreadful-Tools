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
    print('Got status with: {0}'.format(data))
    return data

@WEBHOOK.hook(event_type='check_suite')
def on_check_suite(data):
    print('Got check_suite with: {0}'.format(data))
    return data

@WEBHOOK.hook(event_type='pull_request')
def on_pull_request(data):
    org, repo, pr_number = webhooks.parse_pr_url(data['pull_request']['url'])
    print([org, repo, pr_number])
    if data['action'] == 'synchronize' or data['action'] == 'opened':
        webhooks.set_check(data, 'pending', 'Waiting for tests')
