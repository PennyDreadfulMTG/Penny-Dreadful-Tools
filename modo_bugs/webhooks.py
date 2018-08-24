from github_webhook import Webhook

from shared import configuration
from shared_web.flask_app import PDFlask
from . import update, repo

APP = PDFlask(__name__)
WEBHOOK = Webhook(APP, endpoint='/api/github')

@APP.route('/')
def home():
    return 'build-commit-id: ' + APP.config['commit-id']

def get_number(url: str) -> int:
    split_url = url.split('/')
    return int(split_url[7])


@WEBHOOK.hook(event_type='issues')
def on_issues(data):
    if data['sender']['login'] == configuration.get_str('github_user'):
        return
    number = get_number(data['pull_request']['url'])
    issue = repo.get_repo().get_issue(number)
    update.process_issue(issue)
