from functools import wraps
from typing import Callable

from flask import redirect, request, session, url_for

from decksite.data import person


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
