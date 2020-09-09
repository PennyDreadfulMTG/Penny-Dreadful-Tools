import json
from typing import Dict, List

from flask import url_for

from decksite.data import archetype, person
from magic import fetcher, oracle
from shared import configuration

REQUIRES_APP_CONTEXT = True

def run() -> None:
    urls = archetypes() + cards() + people() + resources()
    write_typeahead(urls)

def archetypes() -> List[Dict[str, str]]:
    urls = []
    archs = archetype.load_archetypes()
    for a in archs:
        urls.append({'name': a.name, 'type': 'Archetype', 'url': url_for('archetype', archetype_id=a.name)})
    return urls

def cards() -> List[Dict[str, str]]:
    urls = []
    for name in oracle.cards_by_name():
        urls.append({'name': name, 'type': 'Card', 'url': url_for('card', name=name)})
    return urls

def people() -> List[Dict[str, str]]:
    urls = []
    for p in person.load_people():
        urls.append({'name': p.name, 'type': 'Person', 'url': url_for('person', mtgo_username=p.name)})
    return urls

def resources() -> List[Dict[str, str]]:
    urls = []
    for category, entries in fetcher.resources().items():
        for name, url in entries.items():
            urls.append({'name': f'Resources – {category} – {name}', 'type': 'Resource', 'url': url})
    return urls

def write_typeahead(urls: List[Dict[str, str]]) -> None:
    f = open(configuration.get_str('typeahead_data_path'), 'w')
    f.write(json.dumps(urls))
