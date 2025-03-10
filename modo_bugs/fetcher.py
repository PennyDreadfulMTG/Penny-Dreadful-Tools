import json
import logging
import os
import re
import sys
import time

import attrs
from bs4 import BeautifulSoup
from bs4.element import Tag

from shared import configuration, fetch_tools, lazy

BUG_REPORTS_FORUM_BASE_URL = 'https://forums.mtgo.com'
BUG_REPORT_FORUM_BASE_PATH = '/index.php?forums/bug-reports.16/'

logger = logging.getLogger(__name__)

@attrs.define
class ForumPost:
    title: str
    label: str | None
    url: str
    # votes: str

def search_scryfall(query: str) -> tuple[int, list[str], list[str]]:
    """Returns a tuple. First member is an integer indicating how many cards match the query total,
       second member is a list of card names up to the maximum that could be fetched in a timely fashion."""
    if query == '':
        return 0, [], []
    logger.info(f'Searching scryfall for `{query}`')
    result_json = fetch_tools.fetch_json('https://api.scryfall.com/cards/search?q=' + fetch_tools.escape(query), character_encoding='utf-8')
    if 'code' in result_json.keys():  # The API returned an error
        if result_json['status'] == 404:  # No cards found
            return 0, [], []
        logger.error('Error fetching scryfall data:\n', result_json)
        return 0, [], []
    for warning in result_json.get('warnings', []):  # scryfall-provided human-readable warnings
        logger.warning(warning)
    result_data = result_json['data']
    result_data.sort(key=lambda x: x['legalities']['penny'])

    def get_frontside(scr_card: dict) -> str:
        """If card is transform, returns first name. Otherwise, returns name.
        This is to make sure cards are later found in the database"""
        if scr_card['layout'] in ['transform', 'flip', 'modal_dfc']:
            return scr_card['card_faces'][0]['name']
        return scr_card['name']
    result_cardnames = [get_frontside(obj) for obj in result_data]
    return result_json['total_cards'], result_cardnames, result_json.get('warnings', [])

def catalog_cardnames() -> list[str]:
    result_json = fetch_tools.fetch_json('https://api.scryfall.com/catalog/card-names')
    names: list[str] = result_json['data']
    for n in names:
        if ' // ' in n:
            names.extend(n.split(' // '))
    return names

def update_redirect(file: str, title: str, redirect: str, **kwargs: str) -> bool:
    text = f'---\ntitle: {title}\nredirect_to:\n - {redirect}\n'
    for key, value in kwargs.items():
        text += f'{key}: {value}\n'
    text = text + '---\n'
    fname = f'{file}.md'
    if not os.path.exists(fname):
        bb_jekyl = open(fname, mode='w')
        bb_jekyl.write('')
        bb_jekyl.close()
    bb_jekyl = open(fname)
    orig = bb_jekyl.read()
    bb_jekyl.close()
    if orig != text:
        logger.info(f'New {file} update!')
        bb_jekyl = open(fname, mode='w')
        bb_jekyl.write(text)
        bb_jekyl.close()
        return True
    if 'always-scrape' in sys.argv:
        return True
    return False

def find_announcements() -> tuple[str | None, bool]:
    articles = [a for a in get_article_archive() if is_announcement(a)]
    if not articles:
        return (None, False)
    (title, link) = articles[0]
    logger.info(f'Found: {title} ({link})')
    time.sleep(1)
    bn = 'PATCH NOTES' in fetch_tools.fetch(link)
    new = update_redirect('announcements', title, link, has_build_notes=str(bn))
    return (link, new)

def is_announcement(a: tuple[str, str]) -> bool:
    if a[0].startswith('Magic Online Weekly Announcements'):
        return True
    if a[0].startswith('Magic Online Announcements'):
        return True
    return False

def parse_article_item_extended(a: Tag) -> tuple[Tag, str]:
    title = a.find_all('h3')[0]
    link = 'https://www.mtgo.com' + a.find_all('a')[0]['href']  # type: ignore
    return (title, link)  # type: ignore

@lazy.lazy_property
def get_article_archive() -> list[tuple[str, str]]:
    try:
        html = fetch_tools.fetch('https://www.mtgo.com/archive')
    except fetch_tools.FetchException:
        html = fetch_tools.fetch('http://magic.wizards.com/en/articles/archive/')
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', class_='article-link')
    if links:
        return [parse_article_item_extended(a) for a in links]  # type: ignore
    scripts = soup.find_all('script')
    findblob = re.compile(r'window.DGC.archive.articles = (.*?}]);', re.MULTILINE)
    for s in scripts:
        if (m := findblob.search(s.contents[0])):  # type: ignore
            blob = m.group(1)
            j = json.loads(blob)
            return [(p['title'], 'https://www.mtgo.com/news/' + p['pageName']) for p in j]
    return []

def get_daybreak_label(url: str) -> str | None:
    time.sleep(1)
    html = fetch_tools.fetch(url)
    soup = BeautifulSoup(html, 'html.parser')
    label = soup.find('span', class_='label--primary')
    if label:
        return label.text
    label = soup.find('span', class_='label--accent')
    if label:
        return label.text
    label = soup.find('span', class_='label--yellow')
    if label:
        return label.text
    label = soup.find('span', class_='label')
    if label:
        return label.text

    return None

def get_all_forum_posts() -> list[ForumPost]:
    posts = []
    sections = get_section_urls()
    for url in sections:
        logger.info(f'Going to get all threads in section {url}')
        posts += get_forum_posts(url)
    return posts

def get_section_urls() -> list[str]:
    html = fetch_tools.fetch(BUG_REPORTS_FORUM_BASE_URL + BUG_REPORT_FORUM_BASE_PATH)
    soup = BeautifulSoup(html, 'html.parser')
    section_urls = []

    for node in soup.find_all('a', class_='subNodeLink--forum'):
        url = BUG_REPORTS_FORUM_BASE_URL + node['href']  # type: ignore
        section_urls.append(url)

    for node in soup.find_all('div', class_='node--forum'):
        url = BUG_REPORTS_FORUM_BASE_URL + node.find('h3', class_='node-title').find('a')['href']  # type: ignore
        section_urls.append(url)

    return section_urls

def get_forum_posts(url: str) -> list[ForumPost]:
    time.sleep(1)  # Try not to get blocked by the Daybreak forums.
    html = fetch_tools.fetch(url)
    soup = BeautifulSoup(html, 'html.parser')
    posts = []
    threads = soup.find_all('div', class_='structItem--thread')
    for p in threads:
        post: Tag = p  # type: ignore
        label = None
        # votes = post.find('span', class_='js-voteCount').text
        title = post.find('div', class_='structItem-title')
        t = title.find('a')  # type: ignore
        if t.attrs['href'].startswith('/index.php?forums'):
            label = t.text
            t = t.find_next_sibling('a')
        url = 'https://forums.mtgo.com' + t.attrs['href']
        name = t.text
        posts.append(ForumPost(name, label, url))
    next = soup.find('a', class_='pageNav-jump--next')
    if next is not None:
        logger.info(f'Next page: {next.attrs["href"]}')  # type: ignore
        url = 'https://forums.mtgo.com' + next.attrs['href']  # type: ignore
        posts.extend(get_forum_posts(url))
    return posts

def forum_to_discord(post: ForumPost) -> None:
    """Post to Discord webhook when new posts are flagged by Daybreak"""
    print(f'New Forum Post:  {post}')
    embed = {
        'title': f'New forum post marked "{post.label}"',
        'type': 'rich',
        'description': f'{post.title}',
        'url': post.url,
    }
    fetch_tools.post_discord_webhook(
        configuration.bugs_webhook_id.value,
        configuration.bugs_webhook_token.value,
        embeds=[embed],
        username='MTGO Forums',
        avatar_url='https://magic.wizards.com/sites/mtg/files/styles/auth_small/public/images/person/wizards_authorpic_larger.jpg',
    )
