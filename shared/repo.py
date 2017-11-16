from github import Github

from shared import configuration

def create_issue(title, author, location='Discord', repo='PennyDreadfulMTG/Penny-Dreadful-Tools'):
    if configuration.get('github_user') is None or configuration.get('github_password') is None:
        return None
    if title is None or title == '':
        return None
    g = Github(configuration.get('github_user'), configuration.get('github_password'))
    repo = g.get_repo(repo)
    body = ''
    if '\n' in title:
        title, body = title.split('\n', 1)
        body += '\n\n'
    body += 'Reported on {location} by {author}'.format(location=location, author=author)
    issue = repo.create_issue(title=title, body=body)
    return issue
