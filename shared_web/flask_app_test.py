from typing import Any
from unittest import mock

import pytest

from shared_web import oauth
from shared_web.flask_app import PDFlask


@pytest.fixture
def app() -> PDFlask:
    flask_app = PDFlask(__name__)
    flask_app.config['SECRET_KEY'] = 'test'

    @flask_app.route('/')
    def home() -> str:
        return ''

    @flask_app.route('/destination/')
    def destination() -> str:
        return ''

    return flask_app


@pytest.mark.parametrize('target', [
    'https://attacker.example/phishing',
    '//attacker.example/phishing',
    r'/\\attacker.example/phishing',
])
def test_logout_does_not_redirect_to_an_external_target(app: PDFlask, target: str) -> None:
    response = app.test_client().get('/logout/', query_string={'target': target})

    assert response.location == '/'


@pytest.mark.parametrize('target,expected', [
    ('destination', '/destination/'),
    ('/destination/?tab=details', '/destination/?tab=details'),
    ('https://localhost/destination/?tab=details', '/destination/?tab=details'),
])
def test_logout_redirects_to_a_local_target(app: PDFlask, target: str, expected: str) -> None:
    response = app.test_client().get('/logout/', query_string={'target': target}, base_url='https://localhost')

    assert response.location == expected


def test_authentication_does_not_save_an_external_target(app: PDFlask) -> None:
    client: Any = app.test_client()
    with mock.patch.object(oauth, 'setup_authentication', return_value=('https://discord.example/auth', 'state')):
        client.get('/authenticate/', query_string={'target': 'https://attacker.example/phishing'})

    with client.session_transaction() as session:
        assert 'target' not in session


def test_authentication_saves_a_local_target_as_a_path(app: PDFlask) -> None:
    client: Any = app.test_client()
    with mock.patch.object(oauth, 'setup_authentication', return_value=('https://discord.example/auth', 'state')):
        client.get('/authenticate/', query_string={'target': 'https://localhost/destination/?tab=details'}, base_url='https://localhost')

    with client.session_transaction() as session:
        assert session['target'] == '/destination/?tab=details'


def test_authentication_callback_does_not_redirect_to_an_external_target(app: PDFlask) -> None:
    client: Any = app.test_client()
    with client.session_transaction() as session:
        session['target'] = 'https://attacker.example/phishing'

    with mock.patch.object(oauth, 'setup_session'):
        response = client.get('/authenticate/callback/')

    assert response.location == '/'
    with client.session_transaction() as session:
        assert 'target' not in session
