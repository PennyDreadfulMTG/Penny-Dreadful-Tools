import re
import sys
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, Comment
from bs4.element import Tag
from github.Issue import Issue

from . import repo
from .strings import BBT_REGEX, remove_smartquotes, strip_squarebrackets


def main() -> None:
    print('Fetching http://magic.wizards.com/en/articles/archive/184956')
    soup = BeautifulSoup(requests.get('http://magic.wizards.com/en/articles/archive/184956').text, 'html.parser')
    articles = [parse_article_item_extended(a) for a in soup.find_all('div', class_='article-item-extended')]
    bug_blogs = [a for a in articles if str(a[0].string).startswith('Magic Online Bug Blog')]
    print('scraping {0} ({1})'.format(bug_blogs[0][0], bug_blogs[0][1]))
    new = update_redirect(bug_blogs[0][0].text, bug_blogs[0][1])
    if new:
        scrape_bb(bug_blogs[0][1])

def update_redirect(title: str, redirect: str) -> bool:
    text = '---\ntitle: {title}\nredirect_to:\n - {url}\n---\n'.format(title=title, url=redirect)
    bb_jekyl = open('bug_blog.md', mode='r')
    orig = bb_jekyl.read()
    bb_jekyl.close()
    if orig != text:
        print('New bug blog update!')
        sys.argv.append('check-missing') # This might be a bad idea
        bb_jekyl = open('bug_blog.md', mode='w')
        bb_jekyl.write(text)
        bb_jekyl.close()
        return True
    if 'always-scrape' in sys.argv:
        return True
    return False

def parse_article_item_extended(a: Tag) -> Tuple[Tag, str]:
    title = a.find_all('h3')[0]
    link = 'http://magic.wizards.com' + a.find_all('a')[0]['href']
    return (title, link)

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
            bbt = remove_smartquotes(item.get_text())

            issue = find_issue_by_code(bbt)
            if issue is not None:
                if not ('From Bug Blog' in [i.name for i in issue.labels]):
                    print('Adding Bug Blog to labels')
                    issue.add_to_labels('From Bug Blog')
            elif find_issue_by_name(bbt):
                print('Already exists.')
            else:
                print('Creating new issue')
                text = 'From Bug Blog.\nAffects: \n<!-- Images -->\nBug Blog Text: {0}'.format(bbt)
                repo.get_repo().create_issue(bbt, body=remove_smartquotes(text), labels=['From Bug Blog'])

def get_cards_from_string(item: str) -> List[str]:
    cards = re.findall(r'\[?\[([^\]]*)\]\]?', item)
    cards = [c for c in cards]
    return cards

def parse_knownbugs(b: Tag) -> None:
    # attempt to find all the fixed bugs
    all_codes = b.find_all(string=lambda text: isinstance(text, Comment))
    all_codes = [str(code).replace('\t', ' ') for code in all_codes]
    for issue in repo.get_repo().get_issues():
        # code = re.search(CODE_REGEX, issue.body, re.MULTILINE)
        bbt = re.search(BBT_REGEX, issue.body, re.MULTILINE)
        if bbt is None:
            cards = get_cards_from_string(issue.title)
            if 'From Bug Blog' in [i.name for i in issue.labels]:
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
                if not ('From Bug Blog' in [i.name for i in issue.labels]):
                    issue.add_to_labels('From Bug Blog')
            continue
        else:
            if 'Invalid Bug Blog' in [i.name for i in issue.labels]:
                issue.remove_from_labels('Invalid Bug Blog')

        if 'From Bug Blog' in [i.name for i in issue.labels]:
            # Don't check for Bug Blog Text if it's not marked as a BB issue (Maybe because it was reopened)
            if bbt is not None:
                text = remove_smartquotes(bbt.group(1).strip())
                for row in b.find_all('tr'):
                    data = row.find_all('td')
                    rowtext = remove_smartquotes(data[1].text.strip())
                    if rowtext == text:
                        break
                    elif strip_squarebrackets(rowtext) == strip_squarebrackets(text):
                        # Fix this
                        print("Issue #{id}'s bug blog text has differing autocard notation.".format(id=issue.number))
                        body = re.sub(BBT_REGEX, 'Bug Blog Text: {0}'.format(rowtext), issue.body, flags=re.MULTILINE)
                        if issue.body != body:
                            issue.edit(body=body)
                            print('Updated to `{0}`'.format(rowtext))
                        break
                else:
                    print('{id} is fixed!'.format(id=issue.number))
                    repo.create_comment(issue, 'This bug has been removed from the bug blog!')
                    issue.edit(state='closed')

    if 'check-missing' in sys.argv:
        # This is very expensive.
        for row in b.find_all('tr'):
            data = row.find_all('td')
            row_text = data[1].text.strip()
            if row_text == 'Description':
                # BS4 is bad.
                continue
            if find_issue_by_code(row_text):
                continue
            print('Could not find issue for `{row}`'.format(row=row_text))
            text = 'From Bug Blog.\nBug Blog Text: {0}'.format(row_text)
            repo.get_repo().create_issue(remove_smartquotes(row_text), body=remove_smartquotes(text), labels=['From Bug Blog'])


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
            if not 'From Bug Blog' in [i.name for i in issue.labels]:
                # Only bug blog issues have bug blog data
                repo.set_issue_bbt(issue.number, None)
                continue
            icode = repo.ISSUE_CODES.get(issue.number, None)
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

if __name__ == '__main__':
    main()
