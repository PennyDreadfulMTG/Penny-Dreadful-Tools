import urllib

from flask import redirect, request, session, url_for

from shared_web import oauth

from . import APP


@APP.route('/authenticate/')
def authenticate():
    target = request.args.get('target')
    authorization_url, state = oauth.setup_authentication()
    session['oauth2_state'] = state
    if target is not None:
        session['target'] = target
    return redirect(authorization_url)

@APP.route('/authenticate/callback/')
def authenticate_callback():
    if request.values.get('error'):
        return redirect(url_for('unauthorized', error=request.values['error']))
    oauth.setup_session(request.url)
    url = session.get('target')
    if url is None:
        url = url_for('home')
    session['target'] = None
    return redirect(url)

@APP.route('/logout/')
def logout():
    oauth.logout()
    target = request.args.get('target', 'home')
    if bool(urllib.parse.urlparse(target).netloc):
        return redirect(target)
    return redirect(url_for(target))
