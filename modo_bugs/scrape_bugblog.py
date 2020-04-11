import re
from typing import List, Match, Optional

import requests
from bs4 import BeautifulSoup, Comment
from bs4.element import Tag
from github.Issue import Issue

from . import fetcher, repo, strings
from .strings import BBT_REGEX, strip_squarebrackets


def main(changes: List[str]) -> None:
    (link, new) = fetcher.find_bug_blog()
    if new and link is not None:
        scrape_bb(link)
        changes.append('* New Bug Blog')


def scrape_bb(url: str) -> None:
    soup = BeautifulSoup(requests.get(url).text, 'html.parser')
    for b in soup.find_all('div', class_='collapsibleBlock'):
        parse_block(b)

def parse_block(collapsible_block: Tag) -> None:
    title = collapsible_block.find_all('h2')[0].get_text()
    print(title)
    handle_autocards(collapsible_block)
    if title == 'Change Log':
        parse_changelog(collapsible_block)
    elif title == 'Known Issues List':
        parse_knownbugs(collapsible_block)
    else:
        print('Unknown block: {0}'.format(title))

def parse_changelog(collapsible_block: Tag) -> None:
    # They never show Fixed bugs in the Bug Blog anymore.  Fixed bugs are now listed on the Build Notes section of MTGO weekly announcements.
    # This is frustrating.
    for added in collapsible_block.find_all('ul'):
        for item in added.find_all('li'):
            print(item)
            bbt = strings.remove_smartquotes(item.get_text())

            issue = find_issue_by_code(bbt)
            if issue is not None:
                if not repo.is_issue_from_bug_blog(issue):
                    print('Adding Bug Blog to labels')
                    issue.add_to_labels('From Bug Blog')
            elif find_issue_by_name(bbt):
                print('Already exists.')
            else:
                print('Creating new issue')
                text = 'From Bug Blog.\nBug Blog Text: {0}'.format(bbt)
                repo.get_repo().create_issue(bbt, body=strings.remove_smartquotes(text), labels=['From Bug Blog'])

def parse_knownbugs(b: Tag) -> None:
    # attempt to find all the fixed bugs
    all_codes = b.find_all(string=lambda text: isinstance(text, Comment))
    all_codes = [str(code).replace('\t', ' ') for code in all_codes]
    for issue in repo.get_repo().get_issues():
        # code = re.search(CODE_REGEX, issue.body, re.MULTILINE)
        bbt = re.search(BBT_REGEX, issue.body, re.MULTILINE)
        if bbt is None:
            cards = strings.get_cards_from_string(issue.title)
            if repo.is_issue_from_bug_blog(issue):
                find_bbt_in_body_or_comments(issue)
                find_bbt_in_issue_title(issue, b)
                bbt = re.search(BBT_REGEX, issue.body, re.MULTILINE)
                if bbt is None:
                    print('Issue #{id} {cards} has no Bug Blog text!'.format(id=issue.number, cards=cards))
                    issue.add_to_labels('Invalid Bug Blog')
                continue

            if not cards:
                continue
            lines = b.find_all(string=re.compile(r'\[' + cards[0] + r'\]'))
            if not lines:
                continue
            for line in lines:
                parent = line.parent
                bb_text = parent.get_text().strip()
                if find_issue_by_code(bb_text) is not None:
                    print('Already assigned.')
                    continue
                text = ''.join(parent.strings)
                print(text)
                repo.create_comment(issue, 'Found in bug blog.\nBug Blog Text: {0}'.format(text))
                if not repo.is_issue_from_bug_blog(issue):
                    issue.add_to_labels('From Bug Blog')
            continue
        if 'Invalid Bug Blog' in [i.name for i in issue.labels]:
            issue.remove_from_labels('Invalid Bug Blog')

        if repo.is_issue_from_bug_blog(issue):
            # Don't check for Bug Blog Text if it's not marked as a BB issue (Maybe because it was reopened)
            check_if_removed_from_bugblog(bbt, b, issue)

    check_for_missing_bugs(b)

def check_if_removed_from_bugblog(bbt: Match, b: Tag, issue: Issue) -> None:
    if bbt is not None:
        text = strings.remove_smartquotes(bbt.group(1).strip())
        for row in b.find_all('tr'):
            data = row.find_all('td')
            rowtext = strings.remove_smartquotes(data[1].text.strip())
            if rowtext == text:
                break
            if strip_squarebrackets(rowtext) == strip_squarebrackets(text):
                # Fix this
                print("Issue #{id}'s bug blog text has differing autocard notation.".format(id=issue.number))
                old_bbt = strings.get_body_field(issue.body, 'Bug Blog Text')
                body = re.sub(BBT_REGEX, 'Bug Blog Text: {0}'.format(rowtext), issue.body, flags=re.MULTILINE)
                new_bbt = strings.get_body_field(body, 'Bug Blog Text')
                issue.edit(body=body)
                print('Updated to `{0}`'.format(rowtext))
                issue.create_comment(f'Changed bug blog text from `{old_bbt}` to `{new_bbt}`')
                break
        else:
            print('{id} is fixed!'.format(id=issue.number))
            repo.create_comment(issue, 'This bug has been removed from the bug blog!')
            issue.edit(state='closed')

def check_for_missing_bugs(b: Tag) -> None:
    for row in b.find_all('tr'):
        data = row.find_all('td')
        row_text = data[1].text.strip()
        if row_text == 'Description':
            # BS4 is bad.
            continue
        issue = find_issue_by_code(row_text)
        if issue:
            labels = [c.name for c in issue.labels]
            categories = [c for c in labels if c in strings.METACATS]
            if categories:
                continue
            bbcat = re.match(strings.REGEX_BBCAT, data[2].text.strip())
            if bbcat is None:
                continue
            g1 = bbcat.group(1).strip()
            if g1 in strings.METACATS:
                issue.add_to_labels(g1)
                continue
            if bbcat.group(2) is not None:
                g2 = bbcat.group(2).strip()
                if g2 in strings.METACATS:
                    issue.add_to_labels(g2)
                    continue
            print(f'Unknown BBCat: {bbcat.group(0)}')
            continue
        print('Could not find issue for `{row}`'.format(row=row_text))
        text = 'From Bug Blog.\nBug Blog Text: {0}'.format(row_text)
        repo.get_repo().create_issue(strings.remove_smartquotes(row_text), body=strings.remove_smartquotes(text), labels=['From Bug Blog'])


def find_bbt_in_issue_title(issue: Issue, known_issues: Tag) -> None:
    title = strip_squarebrackets(issue.title).replace(' ', '')
    for row in known_issues.find_all('tr'):
        data = row.find_all('td')
        row_text = strip_squarebrackets(data[1].text.strip()).replace(' ', '')
        if row_text == title:
            body = issue.body
            body += '\nBug Blog Text: {0}'.format(data[1].text.strip())
            if body != issue.body:
                issue.edit(body=body)
            return

def handle_autocards(soup: Tag) -> None:
    for link in soup.find_all('a', class_='autocard-link'):
        name = link.get_text()
        link.replace_with('[{0}]'.format(name))

def find_issue_by_code(code: str) -> Issue:
    if code is None:
        return None
    def scan(issue_list: List[Issue]) -> Optional[Issue]:
        for issue in issue_list:
            if not repo.is_issue_from_bug_blog(issue):
                # Only bug blog issues have bug blog data
                repo.set_issue_bbt(issue.number, None)
                continue
            icode = repo.get_issue_bbt(issue)
            if icode == code:
                return issue
            if icode is not None:
                continue
            found = code in issue.body
            if not found:
                icode = find_bbt_in_body_or_comments(issue)
                found = code in issue.body
            if icode is not None:
                repo.set_issue_bbt(issue.number, icode.strip())
            else:
                repo.set_issue_bbt(issue.number, None)
            if found:
                repo.set_issue_bbt(issue.number, code)
                return issue
        return None
    res = scan(repo.get_repo().get_issues(state='open'))
    if res:
        return res
    return scan(repo.get_repo().get_issues(state='closed'))

def find_bbt_in_body_or_comments(issue: Issue) -> Optional[str]:
    body = issue.body
    bbt = re.search(BBT_REGEX, issue.body, re.MULTILINE)
    if not bbt:
        for comment in issue.get_comments():
            if bbt is None:
                bbt = re.search(BBT_REGEX, comment.body, re.MULTILINE)
                if bbt is not None:
                    body += '\nBug Blog Text: {0}'.format(bbt.groups()[0].strip())
    if body != issue.body:
        issue.edit(body=body)
    if bbt is not None:
        return bbt.groups()[0].strip()
    return None

def find_issue_by_name(name: str) -> Issue:
    if name is None: #What?
        return None
    all_issues = repo.get_repo().get_issues(state='all')
    for issue in all_issues:
        if issue.title == name:
            return issue
    return None
