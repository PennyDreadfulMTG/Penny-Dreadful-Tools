import textwrap

from flask import request, session
from github import Github

from shared import configuration

def create_issue(content, author, location='Discord', repo='PennyDreadfulMTG/Penny-Dreadful-Tools'):
    if content is None or content == '':
        return None
    body = ''
    if '\n' in content:
        title, body = content.split('\n', 1)
        body += '\n\n'
    else:
        title = content
    body += 'Reported on {location} by {author}'.format(location=location, author=author)
    if request:
        body += textwrap.dedent("""
            --------------------------------------------------------------------------------
            Request Method: {method}
            Path: {full_path}
            Cookies: {cookies}
            Endpoint: {endpoint}
            View Args: {view_args}
            Person: {id}
            User-Agent: {user_agent}
            Referrer: {referrer}
        """.format(method=request.method, full_path=request.full_path, cookies=request.cookies, endpoint=request.endpoint, view_args=request.view_args, id=session.get('id', 'logged_out'), user_agent=request.headers.get('User-Agent'), referrer=request.referrer))
    print(title + '\n' + body)
    # Only check for github details at the last second to get log output even if github not configured.
    if not configuration.get('github_user') or not configuration.get('github_password'):
        return None
    g = Github(configuration.get('github_user'), configuration.get('github_password'))
    repo = g.get_repo(repo)
    issue = repo.create_issue(title=title, body=body)
    return issue
