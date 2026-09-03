import pytest

from decksite.main import APP
from maintenance import typeahead
from shared.container import Container


def test_people_reads_people_as_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """person.load_people returns a list, not (list, total). Unpacking it crashed the daily job."""
    monkeypatch.setattr(typeahead.person, 'load_people', lambda: [Container({'name': 'SmokeTester'})])
    with APP.test_request_context('/'):
        urls = typeahead.people()
    assert urls == [{'name': 'SmokeTester', 'type': 'Person', 'url': '/people/SmokeTester/'}]
