from github_webhook import Webhook

from shared_web.flask_app import PDFlask

APP = PDFlask(__name__)
WEBHOOK = Webhook(APP, endpoint='/api/github')

@APP.route('/')
def home():
    return 'build-commit-id: ' + APP.config['commit-id']

@WEBHOOK.hook(event_type='issues')
def on_issues(data):
    pass
