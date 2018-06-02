from typing import Tuple
from shared import configuration, lazy
from github import Github
from github.PullRequest import PullRequest
from github.Commit import Commit

@lazy.lazy_property
def get_github() -> Github:
    if not configuration.get_str('github_user') or not configuration.get_str('github_password'):
        return None
    return Github(configuration.get('github_user'), configuration.get('github_password'))

def parse_pr_url(url: str) -> Tuple[str, str, int]:
    splitted_url = url.split('/')
    return splitted_url[4], splitted_url[5], int(splitted_url[7])

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

def set_check(data, status, message):
    commit = load_commit(data)
    status = commit.create_status(state=status, target_url='https://pennydreadfulmagic.com', description=message, context='pdm/automerge')
    print(repr(status))
