import os
import zipfile
from pathlib import Path

import pytest

from magic import geonames
from shared.fetch_tools import FetchException


def geonames_row(
    geoname_id: int,
    name: str,
    ascii_name: str,
    alternate_names: str,
    country: str,
    admin1: str,
    population: int,
    feature_code: str,
    timezone: str,
) -> str:
    fields = [
        str(geoname_id), name, ascii_name, alternate_names, '0', '0', 'P', feature_code,
        country, '', admin1, '', '', '', str(population), '', '0', timezone, '2026-09-01',
    ]
    return '\t'.join(fields)


def build_test_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    archive = tmp_path / 'cities500.zip'
    rows = [
        geonames_row(1, 'London', 'London', 'Londres', 'GB', 'ENG', 8_900_000, 'PPLC', 'Europe/London'),
        geonames_row(2, 'London', 'London', '', 'CA', '08', 422_000, 'PPL', 'America/Toronto'),
        geonames_row(3, 'São Paulo', 'Sao Paulo', 'Sampa', 'BR', '27', 12_400_000, 'PPLA', 'America/Sao_Paulo'),
        geonames_row(4, 'Portland', 'Portland', '', 'US', 'OR', 652_000, 'PPL', 'America/Los_Angeles'),
        geonames_row(5, 'La Paz', 'La Paz', '', 'BO', '04', 812_000, 'PPLC', 'America/La_Paz'),
    ]
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(geonames.ARCHIVE_MEMBER, '\n'.join(rows))
    database = tmp_path / 'cities500.sqlite'
    geonames._build_database(archive, database)
    os.utime(database, None)
    monkeypatch.setattr(geonames.configuration.geonames_database, 'get', lambda: str(database))
    return database


def test_find_prefers_capital_and_population_and_supports_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build_test_database(tmp_path, monkeypatch)

    assert geonames.find('London') == geonames.Place('London', 'GB', 'ENG', 'Europe/London')
    assert geonames.find('sao paulo') == geonames.Place('São Paulo', 'BR', '27', 'America/Sao_Paulo')
    assert geonames.find('Sampa') == geonames.Place('São Paulo', 'BR', '27', 'America/Sao_Paulo')
    assert geonames.find('Portland, OR') == geonames.Place('Portland', 'US', 'OR', 'America/Los_Angeles')
    assert geonames.find('La Paz') == geonames.Place('La Paz', 'BO', '04', 'America/La_Paz')


@pytest.mark.parametrize('query', ['ninja', 'television'])
def test_find_does_not_return_non_places(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    build_test_database(tmp_path, monkeypatch)

    assert geonames.find(query) is None


def test_refresh_failure_uses_a_stale_valid_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = build_test_database(tmp_path, monkeypatch)
    old = database.stat().st_mtime - geonames.REFRESH_INTERVAL.total_seconds() - 1
    os.utime(database, (old, old))

    def fail(_path: Path) -> None:
        raise FetchException('offline')

    monkeypatch.setattr(geonames, '_download_and_build', fail)

    assert geonames.ensure_fresh() == database
    assert geonames.find('London') == geonames.Place('London', 'GB', 'ENG', 'Europe/London')
