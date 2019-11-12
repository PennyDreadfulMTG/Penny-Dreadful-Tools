import codecs
import datetime
import json
import re
import sys
import urllib.parse
from typing import Dict, List, Optional

import requests
from github.Issue import Issue

from shared import configuration
from shared.lazy import lazy_property

from . import fetcher, repo, strings
from .strings import (BAD_AFFECTS_REGEX, BADCATS, CATEGORIES, IMAGES_REGEX,
                      REGEX_CARDREF)


@lazy_property
def cardnames() -> List[str]:
    return fetcher.catalog_cardnames()

@lazy_property
def pd_legal_cards() -> List[str]:
    print('Fetching http://pdmtgo.com/legal_cards.txt')
    return requests.get('http://pdmtgo.com/legal_cards.txt').text.split('\n')

ALL_BUGS: List[Dict] = []

VERIFICATION_BY_ISSUE: Dict[int, str] = {}

if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer) # type: ignore

def main() -> None:
    if configuration.get('github_user') is None or configuration.get('github_password') is None:
        print('Invalid Config')
        sys.exit(1)

    verification_numbers()

    issues = repo.get_repo().get_issues()
    for issue in issues:
        print(issue.title)
        if issue.state == 'open':
            process_issue(issue)

    txt = open('bannable.txt', mode='w')
    pd = open('pd_bannable.txt', mode='w')
    for bug in ALL_BUGS:
        if bug['bannable']:
            txt.write(bug['card'] + '\n')
            if bug['pd_legal']:
                pd.write(bug['card'] + '\n')
    txt.close()
    pd.close()

    bugsjson = open('bugs.json', mode='w')
    json.dump(ALL_BUGS, bugsjson, indent=2)
    bugsjson.close()

def verification_numbers() -> None:
    print('Updating Verification Model')
    project = repo.get_verification_project()
    for col in project.get_columns():
        if col.name == 'Needs Testing':
            continue
        print(f'... {col.name}')
        for card in col.get_cards():
            VERIFICATION_BY_ISSUE[card.get_content().number] = col.name
    print('... Done')


def process_issue(issue: Issue) -> None:
    age = (datetime.datetime.now() - issue.updated_at).days
    if age < 5:
        fix_user_errors(issue)
        apply_screenshot_labels(issue)
    labels = [c.name for c in issue.labels]
    see_also = strings.get_body_field(issue.body, 'See Also')
    cards = get_affects(issue)

    if age < 5:
        check_for_invalid_card_names(issue, cards)
        update_issue_body(issue, cards, see_also)

    pd_legal = ([True for c in cards if c in pd_legal_cards()] or [False])[0]

    if pd_legal and not 'Affects PD' in labels:
        issue.add_to_labels('Affects PD')
    elif not pd_legal and 'Affects PD' in labels:
        issue.remove_from_labels('Affects PD')

    msg = issue.title

    categories = [c for c in labels if c in CATEGORIES]
    if not categories:
        if 'From Bug Blog' in labels:
            cat = 'Unclassified'
        else:
            cat = 'Unconfirmed'
            if not issue.comments:
                print('Issue #{id} was reported {days} ago, and has had no followup.'.format(id=issue.number, days=age))
                if age > 30:
                    issue.create_comment('Closing due to lack of followup.')
                    issue.edit(state='closed')
                    return

        if not 'Unclassified' in labels:
            issue.add_to_labels('Unclassified')
    elif 'Unclassified' in labels:
        print('Removing Unclassified from Issue #{id}'.format(id=issue.number))
        issue.remove_from_labels('Unclassified')
        cat = categories.pop()
    else:
        cat = categories.pop()

    for card in cards:
        bannable = cat in BADCATS and 'Multiplayer' not in labels
        bug = {
            'card': card,
            'description': msg,
            'category': cat,
            'last_updated': str(issue.updated_at),
            'pd_legal': card in pd_legal_cards(),
            'bug_blog': 'From Bug Blog' in labels,
            'breaking': cat in BADCATS,
            'bannable': bannable,
            'url': issue.html_url,
            }
        if 'Multiplayer' in labels:
            bug['multiplayer_only'] = True
        if 'Collection' in labels:
            bug['cade_bug'] = True
        if 'Deck Building' in labels:
            bug['cade_bug'] = True

        age = datetime.datetime.now() - issue.updated_at
        if 'Help Wanted' in labels:
            bug['help_wanted'] = True
        elif age.days > 60:
            bug['help_wanted'] = True

        bug['last_verified'] = VERIFICATION_BY_ISSUE.get(issue.number, None)

        ALL_BUGS.append(bug)

def update_issue_body(issue: Issue, cards: List[str], see_also: Optional[str]) -> None:
    expected = '<!-- Images --> '
    images = re.search(IMAGES_REGEX, issue.body, re.MULTILINE)
    for row in strings.grouper(4, cards):
        expected = expected + '<img src="https://pennydreadfulmagic.com/image/{0}/" height="300px">'.format('|'.join([urllib.parse.quote(c) for c in row if c is not None]))
    if see_also is not None:
        for row in strings.grouper(5, re.findall(REGEX_CARDREF, see_also)):
            expected = expected + '<img src="https://pennydreadfulmagic.com/image/{0}/" height="250px">'.format('|'.join([urllib.parse.quote(c) for c in row if c is not None]))

    if not images:
        print('Adding Images...')
        body = issue.body + '\n' + expected
        issue.edit(body=body)
    elif images.group(0) != expected:
        print('Updating images...')
        body = issue.body.replace(images.group(0), expected)
        issue.edit(body=body)

def check_for_invalid_card_names(issue: Issue, cards: List[str]) -> None:
    labels = [lab.name for lab in issue.labels]
    fail = False
    for c in cards:
        if '//' in c:
            pass
        elif not c in cardnames():
            fail = True
    if fail and not 'Invalid Card Name' in labels:
        issue.add_to_labels('Invalid Card Name')
    elif not fail and 'Invalid Card Name' in labels:
        issue.remove_from_labels('Invalid Card Name')

def get_affects(issue: Issue) -> List[str]:
    affects = strings.get_body_field(issue.body, 'Affects')
    if affects is None:
        title = issue.title # type: str
        affects = title

    return strings.get_cards_from_string(affects)

def fix_user_errors(issue: Issue) -> None:
    body = issue.body
    # People sometimes put the affected cards on the following line. Account for that.
    body = re.sub(BAD_AFFECTS_REGEX, 'Affects: [', body)
    # People sometimes neglect Affects all-together, and only put cards in the title.
    affects = strings.get_body_field(body, 'Affects')
    if affects is None:
        cards = re.findall(REGEX_CARDREF, issue.title)
        body = strings.set_body_field(body, 'Affects', ''.join(['[' + c + ']' for c in cards]))
    if re.search(strings.REGEX_SEARCHREF, body):
        def do_search(m) -> str: # type: ignore
            search = m.group(1)
            n, cards, warnings = fetcher.search_scryfall(search)
            if n == 0 or warnings:
                return m.group(0)
            return ', '.join([f'[{c}]' for c in cards])
        body = re.sub(strings.REGEX_SEARCHREF, do_search, body)

    # People are missing the bullet points, and putting info on the following line instead.
    body = re.sub(r' - \r?\n', '', body)
    # Some people ignore the request for screenshots.
    body = body.replace('(Attach a screenshot or video here)', 'Currently Unconfirmed.')
    if repo.is_issue_from_bug_blog(issue):
        bbt = re.search(strings.BBT_REGEX, issue.body, re.MULTILINE)
        if not get_affects(issue) and bbt:
            cards = strings.get_cards_from_string(bbt.group(0))
            if cards:
                cardlist = ', '.join([f'[{c}]' for c in cards])
                body = strings.set_body_field(body, 'Affects', cardlist)

    # Push changes.
    if body != issue.body:
        issue.edit(body=body)
    # People are putting [cardnames] in square quotes, despite the fact we prefer Affects: now.
    title = strings.strip_squarebrackets(issue.title)
    if title != issue.title:
        print('Changing title of #{0} to "{1}"'.format(issue.number, title))
        issue.edit(title=title)

def apply_screenshot_labels(issue: Issue) -> None:
    labels = [c.name for c in issue.labels]
    has_screenshot = 'Has Screenshot' in labels
    has_video = 'Has Video' in labels

    if '(https://user-images.githubusercontent.com/' in issue.body:
        has_screenshot = True
    if 'https://imgur.com/' in issue.body:
        has_screenshot = True
    if 'https://i.imgur.com' in issue.body:
        has_screenshot = True
    if 'https://youtu.be/' in issue.body:
        has_video = True
    if 'youtube.com/watch' in issue.body:
        has_video = True
    if 'clips.twitch.tv/' in issue.body:
        has_video = True

    if has_screenshot and not 'Has Screenshot' in labels:
        issue.add_to_labels('Has Screenshot')
    if has_screenshot and 'Needs Screenshot' in labels:
        issue.remove_from_labels('Needs Screenshot')

    if has_video and not 'Has Video' in labels:
        issue.add_to_labels('Has Video')
    if has_video and 'Needs Video' in labels:
        issue.remove_from_labels('Needs Video')
    if has_video and 'Needs Screenshot' in labels:
        issue.remove_from_labels('Needs Screenshot')

    if not has_screenshot and not has_video and not 'Needs Screenshot' in labels:
        issue.add_to_labels('Needs Screenshot')
    if has_screenshot and not has_video and not 'Needs Video' in labels:
        issue.add_to_labels('Needs Video')

if __name__ == '__main__':
    main()
