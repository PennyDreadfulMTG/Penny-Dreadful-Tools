"""
Contract tests between the server-rendered pages, the React live tables, and the API they load from.

Every "live" table on the site is an empty <div class="decktable" data-...> that DataManager (shared_web/static/js/datamanager.jsx)
turns into a request to an /api/ endpoint. The browser sends *every* data-* attribute, usually as an empty string, and
nothing in the Python test suite used to make that request, so a server change that treated an empty string as a filter
shipped and emptied /decks/. These tests render the real page against a seeded database, read the data-* attributes off
the real element, build the request exactly as DataManager.load() would, and check that rows come back.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from flask.testing import FlaskClient

from decksite.main import APP
from shared.container import Container

DATAMANAGER_JSX = Path('shared_web/static/js/datamanager.jsx')


@dataclass
class LiveTable:
    page: str
    css_class: str
    endpoint: str
    min_total: int
    fixed_props: dict[str, str] = field(default_factory=dict)  # Props the mounting JSX passes explicitly, before {...e.dataset}.

    def __str__(self) -> str:
        return f'{self.css_class} on {self.page}'


def live_tables(seed: Container) -> list[LiveTable]:
    competition_page = f'/competitions/{seed.competition_id}/'
    person_page = f'/people/{seed.person}/'
    return [
        LiveTable('/decks/', 'decktable', '/api/decks/', seed.num_decks),
        LiveTable('/decks/league/', 'decktable', '/api/decks/', 0),
        LiveTable(person_page, 'decktable', '/api/decks/', 2),
        LiveTable(person_page, 'cardtable', '/api/cards2/', 1),
        LiveTable(person_page, 'headtoheadtable', '/api/h2h/', 1),
        LiveTable(f'/cards/{seed.card_in_two_decks}/', 'decktable', '/api/decks/', 2),
        LiveTable(f'/cards/{seed.card_in_one_deck}/', 'decktable', '/api/decks/', 1),
        LiveTable('/cards/', 'cardtable', '/api/cards2/', 1),
        LiveTable('/people/', 'persontable', '/api/people/', seed.num_people),
        LiveTable(competition_page, 'decktable', '/api/decks/', seed.num_decks),
        LiveTable(competition_page, 'cardtable', '/api/cards2/', 1),
        LiveTable('/metagame/', 'metagamegrid', '/api/archetypes2/', 1, {'initialSortBy': 'quality', 'initialSortOrder': 'AUTO'}),
        LiveTable('/tournaments/leaderboards/', 'leaderboardtable', '/api/leaderboards/', 1),
        LiveTable(f'/archetypes/{seed.archetype_with_two_decks}/', 'decktable', '/api/decks/', 2),
        LiveTable(f'/archetypes/{seed.archetype_with_two_decks}/', 'cardtable', '/api/cards2/', 1),
    ]


def datamanager_request_params() -> dict[str, str]:
    """Parse the `const params = {...}` block in DataManager.load(): request key -> 'props.<name>' or a state variable name."""
    source = DATAMANAGER_JSX.read_text()
    block = re.search(r'const params = \{(.*?)\};', source, re.DOTALL)
    assert block, 'Could not find the params block in DataManager.load()'
    params = {}
    for line in block.group(1).splitlines():
        line = line.strip().rstrip(',')
        if not line:
            continue
        m = re.fullmatch(r'"(\w+)": this\.props\.(\w+)', line)
        if m:
            params[m.group(1)] = f'props.{m.group(2)}'
            continue
        m = re.fullmatch(r'(\w+)', line)
        assert m, f'Unrecognized line in DataManager.load() params: {line!r} - update this test to match'
        params[m.group(1)] = m.group(1)
    return params


def known_prop_names() -> set[str]:
    """Every prop DataManager declares plus every prop any table/grid component reads, so a data-* attribute nothing consumes is caught."""
    source = DATAMANAGER_JSX.read_text()
    block = re.search(r'DataManager\.propTypes = \{(.*?)\};', source, re.DOTALL)
    assert block, 'Could not find DataManager.propTypes'
    names = set(re.findall(r'"(\w+)":', block.group(1)))
    for jsx in DATAMANAGER_JSX.parent.glob('*.jsx'):
        names.update(re.findall(r'\bprops\.(\w+)', jsx.read_text()))
    return names


def dataset_key(attr: str) -> str:
    """data-card-name -> cardName, data-hide-top8 -> hideTop8 (the browser's HTMLElement.dataset conversion)."""
    return re.sub(r'-([a-z])', lambda m: m.group(1).upper(), attr.removeprefix('data-'))


def simulate_datamanager_load(props: dict[str, str]) -> dict[str, Any]:
    """Build the query string DataManager.load() sends for a component with these props, with state as it is on first load."""
    if props.get('leagueOnly'):
        deck_type = 'league'
    elif props.get('tournamentOnly'):
        deck_type = 'tournament'
    else:
        deck_type = 'all'
    state = {
        'deckType': deck_type,
        'page': 0,
        'pageSize': int(props['pageSize']),
        'q': '',
        'sortBy': props.get('initialSortBy'),
        'sortOrder': props.get('initialSortOrder'),
    }
    params = {}
    for key, source in datamanager_request_params().items():
        value = props.get(source.removeprefix('props.')) if source.startswith('props.') else state[source]
        if value is not None:  # axios omits undefined params but sends empty strings.
            params[key] = value
    return params


def find_live_table(client: FlaskClient, table: LiveTable) -> dict[str, str]:
    response = client.get(table.page)
    assert response.status_code == 200, f'{table.page} returned {response.status_code}'
    soup = BeautifulSoup(response.get_data(as_text=True), 'html.parser')
    elements = soup.select(f'div.{table.css_class}')
    assert elements, f'{table.page} does not contain a div.{table.css_class}'
    props = dict(table.fixed_props)
    for attr, value in elements[0].attrs.items():
        if attr.startswith('data-'):
            props[dataset_key(attr)] = value if isinstance(value, str) else ' '.join(value)
    return props


@pytest.mark.functional
def test_every_live_table_loads_rows(seeded_db: Container) -> None:
    client = APP.test_client()
    known_props = known_prop_names()
    failures = []
    for table in live_tables(seeded_db):
        try:
            props = find_live_table(client, table)
        except AssertionError as e:
            failures.append(str(e))
            continue
        unknown = set(props) - known_props
        if unknown:
            failures.append(f'{table}: template passes {sorted(unknown)} which DataManager does not declare in propTypes')
        params = simulate_datamanager_load(props)
        response = client.get(table.endpoint, query_string=params)
        if response.status_code != 200:
            failures.append(f'{table}: GET {table.endpoint} {params} returned {response.status_code}')
            continue
        data = response.get_json()
        if data is None or 'objects' not in data or 'total' not in data:
            failures.append(f'{table}: GET {table.endpoint} {params} did not return objects/total')
            continue
        if data['total'] < table.min_total or len(data['objects']) < min(table.min_total, 1):
            failures.append(f'{table}: expected at least {table.min_total} rows but got total={data["total"]} objects={len(data["objects"])} for GET {table.endpoint} {params}')
    assert not failures, '\n'.join(failures)


@pytest.mark.functional
def test_live_deck_table_filters_still_filter(seeded_db: Container) -> None:
    """The mirror image of the test above: a real filter value must reduce the results, so that "ignore empty filters" never becomes "ignore filters"."""
    client = APP.test_client()
    base = simulate_datamanager_load(find_live_table(client, LiveTable('/decks/', 'decktable', '/api/decks/', 0)))

    def total(**overrides: str) -> int:
        response = client.get('/api/decks/', query_string=base | overrides)
        assert response.status_code == 200
        return int(response.get_json()['total'])

    assert total() == seeded_db.num_decks
    assert total(cardName=seeded_db.card_in_two_decks) == 2
    assert total(cardName=seeded_db.card_in_one_deck) == 1
    assert total(personId=str(seeded_db.person_id)) == 2
    assert total(competitionId=str(seeded_db.competition_id)) == seeded_db.num_decks
    assert total(deckType='league') == 0
    assert total(seasonId='all') == seeded_db.num_decks
