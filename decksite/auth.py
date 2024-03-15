from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import redirect, request, session, url_for
from werkzeug import wrappers

from decksite.data import person, permission
from decksite.data.permission import Permission


def login_required(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args: List[Any], **kwargs: Dict[str, Any]) -> wrappers.Response:
        if session.get('id') is None:
            return redirect(url_for('authenticate', target=request.url))
        return f(*args, **kwargs)
    return decorated_function

def demimod_required(f: Callable[..., wrappers.Response]) -> Callable[..., wrappers.Response]:
    @wraps(f)
    def decorated_function(*args: List[Any], **kwargs: Dict[str, Any]) -> wrappers.Response:
        if session.get('admin') is None and session.get('demimod') is None:
            return redirect(url_for('authenticate', target=request.url))
        if session.get('admin') is False and session.get('demimod') is False:
            return redirect(url_for('unauthorized'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args: List[Any], **kwargs: Dict[str, Any]) -> wrappers.Response:
        if session.get('admin') is None:
            return redirect(url_for('authenticate', target=request.url))
        if session.get('admin') is False:
            return redirect(url_for('unauthorized'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required_no_redirect(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args: List[Any], **kwargs: Dict[str, Any]) -> Tuple[str, int]:
        if not session.get('admin'):
            return '', 403
        return f(*args, **kwargs)
    return decorated_function


def load_person(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args: List[Any], **kwargs: Dict[str, Any]) -> Any:
        if discord_id() is not None:
            p = person.maybe_load_person_by_discord_id(discord_id())
            if p:
                login(p)
        return f(*args, **kwargs)
    return decorated_function


def discord_id() -> Optional[int]:
    return session.get('id')

def person_id() -> Optional[int]:
    return session.get('logged_person_id')

def mtgo_username() -> Optional[str]:
    return session.get('mtgo_username')

def login(p: person.Person) -> None:
    session['logged_person_id'] = p.id
    session['person_id'] = p.id
    session['mtgo_username'] = p.name
    session.permanent = True
    locale: Optional[str] = session.get('discord_locale')
    if locale and p.locale != locale:
        person.set_locale(p.id, locale)

def hide_intro() -> bool:
    return session.get('hide_intro', False)

def check_perms() -> None:
    current_id = discord_id()
    if not current_id:
        return
    changes = permission.permission_changes(current_id)
    if not changes:
        return
    session['admin'] = Permission.ADMIN in changes
    session['demimod'] = Permission.DEMIMOD in changes
    permission.delete_changes(current_id)
