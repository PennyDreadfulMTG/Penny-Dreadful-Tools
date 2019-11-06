import os
import sys
from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup
from bs4.element import Tag

from shared import fetch_tools, lazy


def search_scryfall(query: str) -> Tuple[int, List[str], List[str]]:
    """Returns a tuple. First member is an integer indicating how many cards match the query total,
       second member is a list of card names up to the maximum that could be fetched in a timely fashion."""
    if query == '':
        return 0, [], []
    print(f'Searching scryfall for `{query}`')
    result_json = fetch_tools.fetch_json('https://api.scryfall.com/cards/search?q=' + fetch_tools.escape(query), character_encoding='utf-8')
    if 'code' in result_json.keys(): # The API returned an error
        if result_json['status'] == 404: # No cards found
            return 0, [], []
        print('Error fetching scryfall data:\n', result_json)
        return 0, [], []
    for warning in result_json.get('warnings', []): #scryfall-provided human-readable warnings
        print(warning)
    result_data = result_json['data']
    result_data.sort(key=lambda x: x['legalities']['penny'])

    def get_frontside(scr_card: Dict) -> str:
        """If card is transform, returns first name. Otherwise, returns name.
        This is to make sure cards are later found in the database"""
        #not sure how to handle meld cards
        if scr_card['layout'] in ['transform', 'flip']:
            return scr_card['card_faces'][0]['name']
        return scr_card['name']
    result_cardnames = [get_frontside(obj) for obj in result_data]
    return result_json['total_cards'], result_cardnames, result_json.get('warnings', [])

def catalog_cardnames() -> List[str]:
    result_json = fetch_tools.fetch_json('https://api.scryfall.com/catalog/card-names')
    names: List[str] = result_json['data']
    for n in names:
        if ' // ' in n:
            names.extend(n.split(' // '))
    return names

def update_redirect(file: str, title: str, redirect: str, **kwargs: str) -> bool:
    text = '---\ntitle: {title}\nredirect_to:\n - {url}\n'.format(title=title, url=redirect)
    for key, value in kwargs.items():
        text += f'{key}: {value}\n'
    text = text + '---\n'
    fname = f'{file}.md'
    if not os.path.exists(fname):
        bb_jekyl = open(fname, mode='w')
        bb_jekyl.write('')
        bb_jekyl.close()
    bb_jekyl = open(fname, mode='r')
    orig = bb_jekyl.read()
    bb_jekyl.close()
    if orig != text:
        print(f'New {file} update!')
        bb_jekyl = open(fname, mode='w')
        bb_jekyl.write(text)
        bb_jekyl.close()
        return True
    if 'always-scrape' in sys.argv:
        return True
    return False

def find_bug_blog() -> Tuple[str, bool]:
    bug_blogs = [a for a in get_article_archive() if str(a[0].string).startswith('Magic Online Bug Blog')]
    (title, link) = bug_blogs[0]
    print('Found: {0} ({1})'.format(title, link))
    new = update_redirect('bug_blog', title.text, link)
    return (link, new)

def find_announcements() -> Tuple[str, bool]:
    articles = [a for a in get_article_archive() if str(a[0].string).startswith('Magic Online Announcements')]
    (title, link) = articles[0]
    print('Found: {0} ({1})'.format(title, link))
    bn = 'Build Notes' in fetch_tools.fetch(link)
    new = update_redirect('announcements', title.text, link, has_build_notes=str(bn))
    return (link, new)

def parse_article_item_extended(a: Tag) -> Tuple[Tag, str]:
    title = a.find_all('h3')[0]
    link = 'http://magic.wizards.com' + a.find_all('a')[0]['href']
    return (title, link)

@lazy.lazy_property
def get_article_archive() -> List[Tuple[Tag, str]]:
    try:
        html = fetch_tools.fetch('http://magic.wizards.com/en/articles/archive/184956')
    except fetch_tools.FetchException:
        html = fetch_tools.fetch('http://magic.wizards.com/en/articles/archive/')
    soup = BeautifulSoup(html, 'html.parser')
    return [parse_article_item_extended(a) for a in soup.find_all('div', class_='article-item-extended')]

#pylint: disable=R0913
def post_discord_webhook(webhook_id: str,
                         webhook_token: str,
                         message: str = None,
                         username: str = None,
                         avatar_url: str = None,
                         embeds: List[Dict[str, Any]] = None
                        ) -> bool:
    if webhook_id is None or webhook_token is None:
        return False
    url = 'https://discordapp.com/api/webhooks/{id}/{token}'.format(id=webhook_id, token=webhook_token)
    fetch_tools.post(url, json_data={
        'content': message,
        'username': username,
        'avatar_url': avatar_url,
        'embeds': embeds,
        })
    return True
