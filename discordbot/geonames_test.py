import os
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from discordbot import geonames
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
    admin1 = tmp_path / 'admin1CodesASCII.txt'
    countries = tmp_path / 'countryInfo.txt'
    rows = [
        geonames_row(1, 'London', 'London', 'Londres', 'GB', 'ENG', 8_900_000, 'PPLC', 'Europe/London'),
        geonames_row(2, 'London', 'London', '', 'CA', '08', 422_000, 'PPL', 'America/Toronto'),
        geonames_row(3, 'São Paulo', 'Sao Paulo', 'Sampa', 'BR', '27', 12_400_000, 'PPLA', 'America/Sao_Paulo'),
        geonames_row(4, 'Portland', 'Portland', '', 'US', 'OR', 652_000, 'PPL', 'America/Los_Angeles'),
        geonames_row(5, 'La Paz', 'La Paz', '', 'BO', '04', 812_000, 'PPLC', 'America/La_Paz'),
        geonames_row(6, 'New York City', 'New York City', 'New York', 'US', 'NY', 8_804_190, 'PPL', 'America/New_York'),
        geonames_row(7, 'York', 'York', 'New York', 'US', 'NE', 7_864, 'PPLA2', 'America/Chicago'),
        geonames_row(8, 'Kansas City', 'Kansas City', '', 'US', 'MO', 475_378, 'PPL', 'America/Chicago'),
        geonames_row(9, 'Kansas City', 'Kansas City', '', 'US', 'KS', 152_933, 'PPLA2', 'America/Chicago'),
        geonames_row(10, 'Cambridge', 'Cambridge', '', 'GB', 'ENG', 145_674, 'PPLA2', 'Europe/London'),
        geonames_row(11, 'Cambridge', 'Cambridge', '', 'US', 'MA', 110_402, 'PPL', 'America/New_York'),
        geonames_row(12, 'San Jose', 'San Jose', '', 'US', 'CA', 997_368, 'PPLA2', 'America/Los_Angeles'),
        geonames_row(13, 'San José', 'San Jose', '', 'CR', '08', 335_007, 'PPLC', 'America/Costa_Rica'),
        geonames_row(14, 'Victoria', 'Victoria', '', 'CA', '02', 289_625, 'PPLA', 'America/Vancouver'),
        geonames_row(15, 'Victoria', 'Victoria', '', 'SC', '26', 22_881, 'PPLC', 'Indian/Mahe'),
        geonames_row(16, 'Newcastle', 'Newcastle', '', 'AU', '02', 508_437, 'PPLA2', 'Australia/Sydney'),
        geonames_row(17, 'Newcastle', 'Newcastle', '', 'KN', '05', 493, 'PPLA', 'America/St_Kitts'),
    ]
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(geonames.ARCHIVE_MEMBER, '\n'.join(rows))
    admin1.write_text('\n'.join([
        'US.OR\tOregon\tOregon\t1', 'US.NY\tNew York\tNew York\t2',
        'US.NE\tNebraska\tNebraska\t3', 'US.MO\tMissouri\tMissouri\t4',
        'US.KS\tKansas\tKansas\t5', 'US.MA\tMassachusetts\tMassachusetts\t6',
        'US.CA\tCalifornia\tCalifornia\t7', 'AU.02\tNew South Wales\tNew South Wales\t8',
        'CA.02\tBritish Columbia\tBritish Columbia\t9',
    ]))
    countries.write_text('\n'.join([
        'US\tUSA\t840\tUS\tUnited States', 'GB\tGBR\t826\tUK\tUnited Kingdom',
        'CA\tCAN\t124\tCA\tCanada', 'AU\tAUS\t036\tAS\tAustralia',
        'CR\tCRI\t188\tCS\tCosta Rica', 'SC\tSYC\t690\tSE\tSeychelles',
        'KN\tKNA\t659\tSC\tSaint Kitts and Nevis', 'BR\tBRA\t076\tBR\tBrazil',
        'BO\tBOL\t068\tBL\tBolivia',
    ]))
    database = tmp_path / 'cities500.sqlite'
    geonames._build_database(archive, admin1, countries, database)
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


@pytest.mark.parametrize(
    ('query', 'expected'),
    [
        ('New York', geonames.Place('New York City', 'US', 'NY', 'America/New_York')),
        ('Kansas City, Missouri', geonames.Place('Kansas City', 'US', 'MO', 'America/Chicago')),
        ('Cambridge, Massachusetts', geonames.Place('Cambridge', 'US', 'MA', 'America/New_York')),
        ('San Jose, California', geonames.Place('San Jose', 'US', 'CA', 'America/Los_Angeles')),
        ('Victoria', geonames.Place('Victoria', 'CA', '02', 'America/Vancouver')),
        ('Newcastle, Australia', geonames.Place('Newcastle', 'AU', '02', 'Australia/Sydney')),
    ],
)
def test_find_ranks_real_world_candidates_and_honors_full_qualifiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str, expected: geonames.Place) -> None:
    build_test_database(tmp_path, monkeypatch)

    assert geonames.find(query) == expected


def test_find_does_not_ignore_unknown_qualifier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build_test_database(tmp_path, monkeypatch)

    assert geonames.find('Cambridge, Atlantis') is None


@pytest.mark.parametrize('query', ['ninja', 'television'])
def test_find_does_not_return_non_places(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    build_test_database(tmp_path, monkeypatch)

    assert geonames.find(query) is None


def test_refresh_failure_uses_a_stale_valid_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = build_test_database(tmp_path, monkeypatch)
    old = database.stat().st_mtime - geonames.REFRESH_INTERVAL.total_seconds() - 1
    os.utime(database, (old, old))

    refresh = Mock(side_effect=FetchException('offline'))
    monkeypatch.setattr(geonames, '_download_and_build', refresh)

    assert geonames.ensure_fresh() == database
    refresh.assert_called_once_with(database)
    assert geonames.find('London') == geonames.Place('London', 'GB', 'ENG', 'Europe/London')


def test_fresh_database_does_not_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = build_test_database(tmp_path, monkeypatch)
    refresh = Mock()
    monkeypatch.setattr(geonames, '_download_and_build', refresh)

    assert geonames.ensure_fresh() == database
    refresh.assert_not_called()
