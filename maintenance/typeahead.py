import json

from flask import url_for
from typing import Dict

from decksite.data import archetype, competition, deck, person
from magic import fetcher, oracle
from shared import configuration

REQUIRES_APP_CONTEXT = True

def run() -> None:
    urls = archetypes() + cards() + people()
    write_typeahead(urls)

def cards() -> [Dict[str, Dict[str, str]]]:
    urls = []
    for name in oracle.cards_by_name().keys():
        urls.append({'name': name, 'type': 'Card', 'url': url_for('card', name=name)})
    return urls

def people() -> Dict[str, str]:
    urls = []
    for p in person.load_people():
        urls.append({'name': p.name, 'type': 'Person', 'url': url_for('person', mtgo_username=p.name)})
    return urls

def archetypes() -> Dict[str, str]:
    urls = []
    archs = archetype.load_archetypes()
    for a in archs:
        urls.append({'name': a.name, 'type': 'Archetype', 'url': url_for('archetype', archetype_id=a.name)})
    return urls

def write_typeahead(urls):
    f = open(configuration.get('typeahead_data_path'), 'w')
    f.write(json.dumps(urls))
