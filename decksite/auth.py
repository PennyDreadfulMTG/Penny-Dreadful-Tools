import os
from functools import wraps
from typing import Callable

from flask import redirect, request, session, url_for
from requests_oauthlib import OAuth2Session

from decksite import logger
from decksite.data import person
from shared import configuration

API_BASE_URL = 'https://discordapp.com/api'
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'
OAUTH2_CLIENT_ID = configuration.get('oauth2_client_id')
OAUTH2_CLIENT_SECRET = configuration.get('oauth2_client_secret')

def setup_authentication():
    scope = ['identify', 'guilds']
    discord = make_session(scope=scope)
    return discord.authorization_url(AUTHORIZATION_BASE_URL)

def setup_session(url):
    discord = make_session(state=session.get('oauth2_state'))
    token = discord.fetch_token(
        TOKEN_URL,
        client_secret=OAUTH2_CLIENT_SECRET,
        authorization_response=url)
    session['oauth2_token'] = token
    discord = make_session(token=session.get('oauth2_token'))
    user = discord.get(API_BASE_URL + '/users/@me').json()
    session['id'] = user['id']
    session['discord_id'] = user['id']
    guilds = discord.get(API_BASE_URL + '/users/@me/guilds').json()
    wrong_guilds = False # protect against an unexpected response from discord
    for guild in guilds:
        if isinstance(guild, dict) and 'id' in guild:
            if guild['id'] == configuration.get('guild_id'):
                session['admin'] = (guild['permissions'] & 0x10000000) != 0 # Check for the MANAGE_ROLES permissions on Discord as a proxy for "is admin".
        else:
            wrong_guilds = True
    if wrong_guilds:
        logger.warn("auth.py: unexpected discord response. Guilds: {g}".format(g=guilds))

def make_session(token=None, state=None, scope=None):
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

def token_updater(token):
    session['oauth2_token'] = token

def login_required(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('id') is None:
            return redirect(url_for('authenticate', target=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('admin') is None:
            return redirect(url_for('authenticate', target=request.url))
        elif session.get('admin') is False:
            return redirect(url_for('unauthorized'))
        return f(*args, **kwargs)
    return decorated_function

def logout():
    session['admin'] = None
    session['id'] = None
    session['discord_id'] = None
    session['logged_person_id'] = None
    session['person_id'] = None
    session['mtgo_username'] = None

def redirect_uri():
    uri = url_for('authenticate_callback', _external=True)
    if 'http://' in uri:
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'
    return uri

def discord_id():
    return session.get('id')

def person_id():
    return session.get('logged_person_id')

def mtgo_username():
    return session.get('mtgo_username')

def login(p):
    session['logged_person_id'] = p.id
    session['person_id'] = p.id
    session['mtgo_username'] = p.name

def hide_intro():
    return session.get('hide_intro')

def load_person(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if discord_id() is not None:
            p = person.load_person_by_discord_id(discord_id())
            if p:
                login(p)
        return f(*args, **kwargs)
    return decorated_function
