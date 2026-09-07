"""A bot-local place-to-timezone index built from GeoNames cities500.

GeoNames data is licensed under CC BY 4.0: https://www.geonames.org/
"""
from __future__ import annotations

import csv
import datetime
import io
import logging
import os
import re
import sqlite3
import tempfile
import threading
import unicodedata
import zipfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import requests

from shared import configuration
from shared.fetch_tools import USER_AGENT, FetchException

DOWNLOAD_URL = 'https://download.geonames.org/export/dump/cities500.zip'
ADMIN1_URL = 'https://download.geonames.org/export/dump/admin1CodesASCII.txt'
COUNTRY_URL = 'https://download.geonames.org/export/dump/countryInfo.txt'
ARCHIVE_MEMBER = 'cities500.txt'
REFRESH_INTERVAL = datetime.timedelta(days=7)
SCHEMA_VERSION = '2'

logger = logging.getLogger(__name__)
_refresh_lock = threading.Lock()
_separators = re.compile(r'[^\w]+', re.UNICODE)


@dataclass(frozen=True)
class Place:
    name: str
    country_code: str
    admin1_code: str
    timezone: str

    @property
    def display_name(self) -> str:
        parts = [self.name]
        if self.country_code == 'US' and self.admin1_code:
            parts.append(self.admin1_code)
        if self.country_code:
            parts.append(self.country_code)
        return ', '.join(parts)


def database_path() -> Path:
    return Path(configuration.geonames_database.get()).expanduser()


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize('NFKD', value.casefold())
    without_accents = ''.join(character for character in decomposed if not unicodedata.combining(character))
    return ' '.join(_separators.sub(' ', without_accents).split())


def ensure_fresh(force: bool = False) -> Path:
    path = database_path()
    if not force and _is_fresh(path):
        return path
    with _refresh_lock:
        if not force and _is_fresh(path):
            return path
        usable_old_database = _is_valid_database(path)
        try:
            _download_and_build(path)
        except FetchException:
            if usable_old_database:
                logger.exception('Unable to refresh GeoNames; continuing with the existing database at %s.', path)
                return path
            raise
    return path


def find(query: str) -> Place | None:
    path = ensure_fresh()
    normalized, qualifiers = _query_parts(query)
    if not normalized:
        return None
    with closing(sqlite3.connect(path)) as connection:
        return _find(connection, normalized, qualifiers)


def _query_parts(query: str) -> tuple[str, tuple[str, ...]]:
    stripped = query.strip()
    comma_parts = [part.strip() for part in stripped.split(',') if part.strip()]
    if len(comma_parts) > 1:
        return normalize_name(comma_parts[0]), tuple(normalize_qualifier(part) for part in comma_parts[1:])
    words = stripped.split()
    if len(words) > 1 and words[-1].isupper() and re.fullmatch(r'[A-Z]{2,3}', words[-1]):
        return normalize_name(' '.join(words[:-1])), (normalize_qualifier(words[-1]),)
    return normalize_name(stripped), ()


def normalize_qualifier(value: str) -> str:
    normalized = normalize_name(value)
    compact = normalized.replace(' ', '')
    return compact if compact.isalpha() and len(compact) <= 3 else normalized


def _find(connection: sqlite3.Connection, normalized: str, qualifiers: tuple[str, ...]) -> Place | None:
    qualifier_clauses = []
    parameters: list[str] = [normalized]
    for index, qualifier in enumerate(qualifiers):
        qualifier_clauses.append(f'AND EXISTS (SELECT 1 FROM place_qualifier AS q{index} WHERE q{index}.place_id = p.geoname_id AND q{index}.normalized_qualifier = ?)')
        parameters.append(qualifier)
    row = connection.execute(
        f'''
            SELECT p.name, p.country_code, p.admin1_code, p.timezone
              FROM place_name AS n
              JOIN place AS p ON p.geoname_id = n.place_id
             WHERE n.normalized_name = ? {' '.join(qualifier_clauses)}
             ORDER BY n.priority,
                      p.population * CASE p.feature_code WHEN 'PPLC' THEN 4 WHEN 'PPLA' THEN 4 WHEN 'PPLA2' THEN 2 ELSE 1 END DESC,
                      p.population DESC,
                      p.geoname_id
             LIMIT 1
        ''',
        parameters,
    ).fetchone()
    return Place(*row) if row else None


def _is_fresh(path: Path) -> bool:
    if not _is_valid_database(path):
        return False
    cutoff = datetime.datetime.now(datetime.UTC).timestamp() - REFRESH_INTERVAL.total_seconds()
    return path.stat().st_mtime >= cutoff


def _is_valid_database(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(path)) as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
        return row == (SCHEMA_VERSION,)
    except sqlite3.Error:
        return False


def _download_and_build(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='geonames-', dir=path.parent) as temporary:
            temporary_directory = Path(temporary)
            archive_path = temporary_directory / 'cities500.zip'
            admin1_path = temporary_directory / 'admin1CodesASCII.txt'
            country_path = temporary_directory / 'countryInfo.txt'
            database = temporary_directory / 'cities500.sqlite'
            logger.info('Downloading GeoNames cities500 from %s.', DOWNLOAD_URL)
            _download(DOWNLOAD_URL, archive_path)
            _download(ADMIN1_URL, admin1_path)
            _download(COUNTRY_URL, country_path)
            _build_database(archive_path, admin1_path, country_path, database)
            os.replace(database, path)
    except (OSError, requests.RequestException, sqlite3.Error, UnicodeError, ValueError, zipfile.BadZipFile) as error:
        raise FetchException(f'Unable to update the GeoNames cities500 database: {error}') from error


def _download(url: str, path: Path) -> None:
    with requests.get(url, headers={'User-Agent': USER_AGENT}, stream=True, timeout=(10, 120)) as response:
        response.raise_for_status()
        with path.open('wb') as output:
            for chunk in response.iter_content(1024 * 1024):
                output.write(chunk)


def _build_database(archive_path: Path, admin1_path: Path, country_path: Path, database: Path) -> None:
    count = 0
    admin1_qualifiers = _admin1_qualifiers(admin1_path)
    country_qualifiers = _country_qualifiers(country_path)
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.executescript(
            '''
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            CREATE TABLE place (
                geoname_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                country_code TEXT NOT NULL,
                admin1_code TEXT NOT NULL,
                population INTEGER NOT NULL,
                feature_code TEXT NOT NULL,
                timezone TEXT NOT NULL
            );
            CREATE TABLE place_name (
                normalized_name TEXT NOT NULL,
                place_id INTEGER NOT NULL,
                priority INTEGER NOT NULL,
                PRIMARY KEY (normalized_name, place_id)
            ) WITHOUT ROWID;
            CREATE TABLE place_qualifier (
                normalized_qualifier TEXT NOT NULL,
                place_id INTEGER NOT NULL,
                PRIMARY KEY (normalized_qualifier, place_id)
            ) WITHOUT ROWID;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
            ''',
        )
        with zipfile.ZipFile(archive_path) as archive, archive.open(ARCHIVE_MEMBER) as binary:
            rows = csv.reader(io.TextIOWrapper(binary, encoding='utf-8', newline=''), delimiter='\t')
            for row in rows:
                if len(row) != 19 or not row[17]:
                    continue
                geoname_id = int(row[0])
                connection.execute(
                    'INSERT INTO place VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (geoname_id, row[1], row[8], row[10], int(row[14] or 0), row[7], row[17]),
                )
                aliases: dict[str, int] = {}
                for priority, names in ((0, [row[1]]), (1, [row[2]]), (2, row[3].split(','))):
                    for name in names:
                        normalized = normalize_name(name)
                        if normalized:
                            aliases[normalized] = min(priority, aliases.get(normalized, priority))
                connection.executemany(
                    'INSERT INTO place_name VALUES (?, ?, ?)',
                    ((alias, geoname_id, priority) for alias, priority in aliases.items()),
                )
                qualifiers = country_qualifiers.get(row[8], {normalize_qualifier(row[8])}) | admin1_qualifiers.get(f'{row[8]}.{row[10]}', {normalize_qualifier(row[10])})
                connection.executemany(
                    'INSERT INTO place_qualifier VALUES (?, ?)',
                    ((qualifier, geoname_id) for qualifier in qualifiers if qualifier),
                )
                count += 1
        connection.executemany(
            'INSERT INTO metadata VALUES (?, ?)',
            (
                ('schema_version', SCHEMA_VERSION),
                ('source', DOWNLOAD_URL),
                ('place_count', str(count)),
                ('updated_at', datetime.datetime.now(datetime.UTC).isoformat()),
            ),
        )
        connection.execute('ANALYZE')
    if count == 0:
        raise ValueError('GeoNames archive contained no usable places')


def _admin1_qualifiers(path: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    with path.open(encoding='utf-8') as source:
        for row in csv.reader(source, delimiter='\t'):
            if len(row) < 3 or '.' not in row[0]:
                continue
            code = row[0].split('.', maxsplit=1)[1]
            result[row[0]] = {normalize_qualifier(value) for value in (code, row[1], row[2]) if value}
    return result


def _country_qualifiers(path: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    with path.open(encoding='utf-8') as source:
        for line in source:
            if line.startswith('#'):
                continue
            row = line.rstrip('\n').split('\t')
            if len(row) < 5:
                continue
            result[row[0]] = {normalize_qualifier(value) for value in (row[0], row[1], row[3], row[4]) if value}
    return result
