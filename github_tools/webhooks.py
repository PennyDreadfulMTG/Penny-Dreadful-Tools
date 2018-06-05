from typing import Dict, Tuple

from github import Github
from github.Commit import Commit
from github.PullRequest import PullRequest
from github.Repository import Repository

from shared import configuration, lazy, redis

PDM_CHECK_CONTEXT = 'pdm/automerge'

@lazy.lazy_property
def get_github() -> Github:
    if not configuration.get_str('github_user') or not configuration.get_str('github_password'):
        return None
    return Github(configuration.get('github_user'), configuration.get('github_password'))

def parse_pr_url(url: str) -> Tuple[str, str, int]:
    split_url = url.split('/')
    return split_url[4], split_url[5], int(split_url[7])

def load_pr(data: dict) -> PullRequest:
    org, repo, pr_number = parse_pr_url(data.get('pull_request', data.get('issue'))['url'])
    g = get_github()
    return g.get_repo(f'{org}/{repo}').get_pull(pr_number)

def load_commit(data: dict) -> Commit:
    pr_data = data.get('pull_request')
    if pr_data is None:
        return None
    org, repo, _ = parse_pr_url(pr_data['url'])
    head = pr_data.get('head')
    g = get_github()
    return g.get_repo(f'{org}/{repo}').get_commit(head.get('sha'))

def get_pr_from_status(data) -> PullRequest:
    g = get_github()
    repo = g.get_repo(data['name'])
    return get_pr_from_commit(repo, data['sha'])

def get_pr_from_commit(repo: Repository, sha: str) -> PullRequest:
    cached = redis.get_list(f'github:head:{sha}')
    if cached:
        pr = repo.get_pull(cached)
        if pr.head.sha == sha and pr.state == 'open':
            return pr
    for pr in repo.get_pulls():
        head = pr.head.sha
        redis.store(f'github:head:{head}', pr.number, ex=3600)
        if head == sha:
            return pr
    return None

def set_check(data, status, message):
    commit = load_commit(data)
    return commit.create_status(state=status, description=message, context=PDM_CHECK_CONTEXT)

def check_pr_for_mergability(pr: PullRequest) -> str:
    repo = pr.base.repo
    commit = repo.get_commit(pr.head.sha)
    checks: Dict[str, str] = {}
    for status in commit.get_statuses():
        print(status)
        if status.context == PDM_CHECK_CONTEXT:
            continue
        if checks.get(status.context) is None:
            checks[status.context] = status.state
            if status.state != 'success':
                commit.create_status(state='pending', description=f'Waiting for {status.context}', context=PDM_CHECK_CONTEXT)
                return f'Merge blocked by {status.context}'
    print(checks)
    if not 'merge when ready' in [l.name for l in pr.as_issue().labels]:
        commit.create_status(state='pending', description='Waiting for "Ready to Merge"', context=PDM_CHECK_CONTEXT)

    commit.create_status(state='success', description='Ready to merge', context=PDM_CHECK_CONTEXT)
    pr.merge()
    return 'good to merge'
