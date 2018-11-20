from github_webhook import Webhook

from shared import configuration
from shared_web.flask_app import PDFlask

from . import repo, update

APP = PDFlask(__name__)
WEBHOOK = Webhook(APP, endpoint='/api/github')

@APP.route('/')
def home() -> str:
    return 'bughooks: build-commit-id: ' + APP.config['commit-id']

@APP.route('/api/reset/')
def reset() -> str:
    try:
        import uwsgi
        uwsgi.reload()
        return 'Ok'
    except ImportError:
        return 'Not running under uwsgi'


def get_number(url: str) -> int:
    split_url = url.split('/')
    return int(split_url[7])


@WEBHOOK.hook(event_type='issues')
def on_issues(data: dict) -> str:
    if data['sender']['login'] == configuration.get_str('github_user'):
        return 'Ignoring self'
    number = get_number(data['issue']['url'])
    issue = repo.get_repo().get_issue(number)
    update.process_issue(issue)
    return 'done'
