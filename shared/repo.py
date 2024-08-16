import datetime
import hashlib
import sys
import textwrap
import traceback

import traceback_with_variables
from flask import request, session
from github import Github, Issue, PullRequest
from github.GithubException import GithubException
from requests.exceptions import RequestException
from traceback_with_variables.core import Format

from shared import configuration, dtutil

GITHUB_MAX_TITLE_LEN = 256
GITHUB_MAX_BODY_LEN = 65536

REDACTED_STRINGS = set()
if configuration.token.value:
    REDACTED_STRINGS.add(configuration.token.value)
if configuration.mysql_passwd.value:
    REDACTED_STRINGS.add(configuration.mysql_passwd.value)
if configuration.oauth2_client_secret.value:
    REDACTED_STRINGS.add(configuration.oauth2_client_secret.value)

def create_issue(content: str,
                 author: str,
                 location: str = 'Discord',
                 repo_name: str = 'PennyDreadfulMTG/Penny-Dreadful-Tools',
                 exception: BaseException | None = None) -> Issue.Issue | None:
    labels: list[str] = []
    issue_hash = None
    if content is None or content == '':
        return None
    body = ''
    if '\n' in content:
        title, body = content.split('\n', 1)
        body += '\n\n'
    else:
        title = content
    body += f'Reported on {location} by {author}\n\n'
    if exception:
        body += '<details><summary>\n'
        body += exception.__class__.__name__ + '\n'
        body += str(exception) + '\n'
        body += '</summary>\n\n'
        fmt = Format(custom_var_printers=[
            ('headers', '...redacted...'),
        ])
        pretty = traceback_with_variables.format_exc(exception, fmt=fmt)
        body += 'Stack Trace:\n\n```\n\nPython traceback\n\n' + ''.join(pretty) + '\n\n```\n\n</details>\n\n'
        issue_hash = hashlib.sha1(''.join(pretty).encode()).hexdigest()
        body += f'Exception_hash: {issue_hash}\n'
    elif repo_name == 'PennyDreadfulMTG/perf-reports':
        stack = traceback.extract_stack()[:-3]
        pretty = traceback.format_list(stack)
        if request:
            pretty.append(request.full_path)
        issue_hash = hashlib.sha1(''.join(pretty).encode()).hexdigest()
        body += f'Location Hash: {issue_hash}\n'

    if request:
        body += '<details><summary><strong>Request Data</strong></summary>\n\n```\n'
        body += textwrap.dedent("""
            Request Method: {method}
            Path: {full_path}
            Cookies: {cookies}
            Endpoint: {endpoint}
            View Args: {view_args}
            Person: {id}
            Referrer: {referrer}
            Request Data: {safe_data}
        """.format(method=request.method, full_path=request.full_path, cookies=request.cookies, endpoint=request.endpoint, view_args=request.view_args, id=session.get('id', 'logged_out'), referrer=request.referrer, safe_data=str(safe_data(request.form))))
        body += '\n'.join([f'{k}: {v}' for k, v in request.headers])
        body += '\n```\n\n</details>\n\n'
        ua = request.headers.get('User-Agent', '')
        if ua == 'pennydreadfulmagic.com cache renewer':
            labels.append(ua)
        elif 'YandexBot' in ua or 'Googlebot' in ua or 'bingbot' in ua:
            labels.append('Search Engine')

    print(title + '\n' + body, file=sys.stderr)
    if not configuration.create_github_issues.value:
        print('Not creating github issue - configured to not do so')
        return None
    # Only check for github details at the last second to get log output even if github not configured.
    if not configuration.get('github_user') or not configuration.get('github_password'):
        print('Not creating github issue - missing username or password')
        return None

    for secret in REDACTED_STRINGS:
        if secret and secret in body:
            body = body.replace(secret, 'REDACTED')

    if len(title) > GITHUB_MAX_TITLE_LEN:
        title = title[0:GITHUB_MAX_TITLE_LEN - 4] + '…'
    if len(body) > GITHUB_MAX_BODY_LEN:
        body = body[0:GITHUB_MAX_BODY_LEN - 4] + '…'
    try:
        g = Github(configuration.get_str('github_user'), configuration.get_str('github_password'))
        git_repo = g.get_repo(repo_name)
        if repo_name == 'PennyDreadfulMTG/perf-reports':
            labels.append(location)
            if exception:
                labels.append(exception.__class__.__name__)
        if issue_hash:
            try:
                issue = g.search_issues(issue_hash, repo=repo_name)[0]
                labelstr = '; '.join(labels)
                issue.create_comment(f'{title}\n\n{body}\n\nLabels: {labelstr}')
                return issue
            except IndexError:
                pass
        issue = git_repo.create_issue(title=title, body=body, labels=labels)
        return issue
    except GithubException as e:
        print(f'Problem creating issue: {e}', file=sys.stderr)
        return None

def safe_data(data: dict[str, str]) -> dict[str, str]:
    safe = {}
    for k, v in data.items():
        if 'oauth' not in k.lower() and 'api_token' not in k.lower():
            safe[k] = v
    return safe

def get_pull_requests(start_date: datetime.datetime,
                      end_date: datetime.datetime,
                      max_pull_requests: int = sys.maxsize,
                      repo_name: str = 'PennyDreadfulMTG/Penny-Dreadful-Tools',
                      ) -> list[PullRequest.PullRequest]:
    gh_user = configuration.get_optional_str('github_user')
    gh_pass = configuration.get_optional_str('github_password')
    if gh_user is None or gh_pass is None:
        return []
    pulls: list[PullRequest.PullRequest] = []
    try:
        g = Github(gh_user, gh_pass)
        git_repo = g.get_repo(repo_name)
        for pull in git_repo.get_pulls(state='closed', sort='updated', direction='desc'):
            if not pull.merged_at:
                continue
            merged_dt = dtutil.UTC_TZ.localize(pull.merged_at)
            updated_dt = dtutil.UTC_TZ.localize(pull.updated_at)
            if merged_dt > end_date:
                continue
            if updated_dt < start_date:
                return pulls
            pulls.append(pull)
            if len(pulls) >= max_pull_requests:
                return pulls
    except RequestException as e:
        print('Github pulls error (request)', e)
    except GithubException as e:
        print('Gihub pulls error (github)', e)
    return pulls

def format_exception(e: Exception) -> str:
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))
