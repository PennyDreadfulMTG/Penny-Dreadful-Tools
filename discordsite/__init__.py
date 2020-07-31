from shared import redis_wrapper as redis
from shared_web.flask_app import PDFlask

APP = PDFlask(__name__)

@APP.route('/')
def home() -> str:
    cid = redis.get_str('discordbot:commit_id')
    return f'discord-commit-id: {cid}'

@APP.route('/reboot', methods=['POST'])
def rotate() -> str:
    redis.store('discordbot:do_reboot', True)
    return 'True'
