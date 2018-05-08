from flask import redirect, request, session, url_for

from shared_web import oauth

from . import APP


@APP.route('/authenticate/')
def authenticate():
    target = request.args.get('target')
    authorization_url, state = oauth.setup_authentication()
    # logsite duplication, see #4743
    session['oauth2_state'] = state
    if target is not None:
        session['target'] = target
    # logsite duplication, see #4743
    return redirect(authorization_url)

@APP.route('/authenticate/callback/')
def authenticate_callback():
    # logsite duplication, see #4743
    if request.values.get('error'):
        return redirect(url_for('unauthorized', error=request.values['error']))
    # logsite duplication, see #4743
    oauth.setup_session(request.url)
    url = session.get('target')
    # logsite duplication, see #4743
    if url is None:
        url = url_for('home')
    # logsite duplication, see #4743
    session['target'] = None
    return redirect(url)
