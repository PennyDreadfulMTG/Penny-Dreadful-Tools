import logging

from bs4 import BeautifulSoup
from bs4.element import Tag

from shared import configuration, fetch_tools

from . import fetcher

logger = logging.getLogger(__name__)

def main(changes: list[str]) -> None:
    (link, new) = fetcher.find_announcements()
    if new and link is not None:
        scrape(link)
        changes.append('* New Magic Online Announcements')


def scrape(url: str) -> None:
    soup = BeautifulSoup(fetch_tools.fetch(url), 'html.parser')
    for b in soup.find_all('h2'):
        parse_header(b)

def parse_header(h: Tag) -> None:
    logger.debug(h)
    txt = h.text
    if 'Downtime' in txt:
        parse_downtimes(h)
    elif txt.startswith('Build Notes') or 'Change Log' in txt or 'PATCH NOTES' in txt:
        parse_build_notes(h)

def parse_build_notes(h: Tag) -> None:
    entries = []
    for n in h.next_elements:
        if isinstance(n, Tag) and n.name == 'li':
            if n.text:
                entries.append(n.text)
        if isinstance(n, Tag) and n.name == 'p':
            if 'posted-in' in n.attrs.get('class', []):
                break
            if n.attrs.get('id', '') == 'down':
                break

    embed = {
        'title': 'MTGO Build Notes',
        'type': 'rich',
        'description': '\n'.join(entries),
        'url': fetcher.find_announcements()[0],
    }
    fetch_tools.post_discord_webhook(
        configuration.bugs_webhook_id.value,
        configuration.bugs_webhook_token.value,
        embeds=[embed],
        username='Magic Online Announcements',
        avatar_url='https://magic.wizards.com/sites/mtg/files/styles/auth_small/public/images/person/wizards_authorpic_larger.jpg',
    )

def parse_downtimes(h: Tag) -> None:
    for n in h.next_elements:
        if isinstance(n, Tag) and n.text:
            with open('downtimes.txt', 'w', encoding='utf-8') as f:
                txt = n.text.strip()
                txt = txt.replace("Please note that there are no more 'extended' or 'normal' downtimes; in the new world with fewer downtimes, they're all the same length of time.", '')
                logger.info(txt)
                f.write(txt)
            break
