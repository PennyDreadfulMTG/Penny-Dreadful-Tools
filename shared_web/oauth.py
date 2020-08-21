import os
from typing import List, Tuple

from flask import session, url_for
from requests_oauthlib import OAuth2Session

from shared import configuration
from shared import logger

API_BASE_URL = 'https://discordapp.com/api'
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'
OAUTH2_CLIENT_ID = configuration.get('oauth2_client_id')
OAUTH2_CLIENT_SECRET = configuration.get('oauth2_client_secret')

def setup_authentication() -> Tuple[str, str]:
    scope = ['identify', 'guilds', 'guilds.join']
    discord = make_session(scope=scope)
    return discord.authorization_url(AUTHORIZATION_BASE_URL)


def setup_session(url: str) -> None:
    discord = make_session(state=session.get('oauth2_state'))
    token = discord.fetch_token(
        TOKEN_URL,
        client_secret=OAUTH2_CLIENT_SECRET,
        authorization_response=url)
    session.permanent = True
    session['oauth2_token'] = token
    discord = make_session(token=session.get('oauth2_token'))
    user = discord.get(API_BASE_URL + '/users/@me').json()
    session['id'] = user['id']
    session['discord_id'] = user['id']
    session['discord_locale'] = user['locale']
    guilds = discord.get(API_BASE_URL + '/users/@me/guilds').json()
    wrong_guilds = False # protect against an unexpected response from discord
    session['in_guild'] = False
    session['admin'] = False
    session['demimod'] = False
    for guild in guilds:
        if isinstance(guild, dict) and 'id' in guild:
            if guild['id'] == configuration.get('guild_id'):
                session['admin'] = (guild['permissions'] & 0x10000000) != 0 # Check for the MANAGE_ROLES permissions on Discord as a proxy for "is admin".
                session['demimod'] = (guild['permissions'] & 0x20000) != 0 # Check for the "Mention @everyone" permissions on Discord as a proxy for "is demimod".
                session['in_guild'] = True
        else:
            wrong_guilds = True
    if wrong_guilds:
        logger.warning('auth.py: unexpected discord response. Guilds: {g}'.format(g=guilds))

def add_to_guild() -> None:
    discord = make_session(token=session.get('oauth2_token'))
    if not session['in_guild']:
        discord.put('/guilds/{guild}/members/{user}'.format(guild=configuration.get('guild_id'), user=session['discord_id']))


def make_session(token: str = None,
                 state: str = None,
                 scope: List[str] = None) -> OAuth2Session:
    return OAuth2Session(
        client_id=OAUTH2_CLIENT_ID,
        token=token,
        state=state,
        scope=scope,
        redirect_uri=redirect_uri(),
        auto_refresh_kwargs={
            'client_id': OAUTH2_CLIENT_ID,
            'client_secret': OAUTH2_CLIENT_SECRET,
        },
        auto_refresh_url=TOKEN_URL,
        token_updater=token_updater)

def token_updater(token: str) -> None:
    session['oauth2_token'] = token

def redirect_uri() -> str:
    uri = url_for('authenticate_callback', _external=True)
    if 'http://' in uri:
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'
    return uri

def logout() -> None:
    session['admin'] = None
    session['demimod'] = None
    session['id'] = None
    session['discord_id'] = None
    session['logged_person_id'] = None
    session['person_id'] = None
    session['mtgo_username'] = None
    session['discord_locale'] = None
