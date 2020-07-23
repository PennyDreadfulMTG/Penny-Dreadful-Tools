from typing import Dict, Optional

from github import Github
from github.Issue import Issue
from github.IssueComment import IssueComment
from github.Project import Project
from github.Repository import Repository

from shared import configuration, decorators
from shared import redis_wrapper as redis

from . import strings

ISSUE_CODES: Dict[int, str] = {}

@decorators.memoize
def get_github() -> Optional[Github]:
    if not configuration.get_str('github_user') or not configuration.get_str('github_password'):
        return None
    return Github(configuration.get_str('github_user'), configuration.get_str('github_password'))

@decorators.memoize
def get_repo() -> Optional[Repository]:
    gh = get_github()
    if gh is not None:
        return gh.get_repo('PennyDreadfulMTG/modo-bugs')
    return None

def get_verification_project() -> Project:
    return get_repo().get_projects()[0]

def create_comment(issue: Issue, body: str) -> IssueComment:
    set_issue_bbt(issue.number, None)
    return issue.create_comment(strings.remove_smartquotes(body))

def set_issue_bbt(number: int, text: Optional[str]) -> None:
    key = f'modobugs:bug_blog_text:{number}'
    if text is None:
        ISSUE_CODES.pop(number, None)
        redis.clear(key)
    else:
        ISSUE_CODES[number] = text
        redis.store(key, text, ex=1200)

def get_issue_bbt(issue: Issue) -> Optional[str]:
    key = f'modobugs:bug_blog_text:{issue.number}'
    bbt = ISSUE_CODES.get(issue.number, None)
    if bbt is not None:
        return bbt
    bbt = redis.get_str(key, ex=1200)
    if bbt is not None:
        return bbt
    return None

def is_issue_from_bug_blog(issue: Issue) -> bool:
    return 'From Bug Blog' in [i.name for i in issue.labels]
