from typing import Tuple
from shared import configuration, lazy, redis
from github import Github
from github.PullRequest import PullRequest
from github.Commit import Commit
from github.Repository import Repository

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
    cached = redis.get_list(f'github-head-{sha}')
    if cached:
        return repo.get_pull(cached)
    for pr in repo.get_pulls():
        head = pr.head.sha
        redis.store(f'github-head-{head}', pr.number)
        if head == sha:
            return pr
    return None

def set_check(data, status, message):
    commit = load_commit(data)
    status = commit.create_status(state=status, target_url='https://pennydreadfulmagic.com', description=message, context='pdm/automerge')

