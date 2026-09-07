"""A small, local place-to-timezone index built from GeoNames cities500.

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
from dataclasses import dataclass
from pathlib import Path

import requests

from shared import configuration
from shared.fetch_tools import USER_AGENT, FetchException

DOWNLOAD_URL = 'https://download.geonames.org/export/dump/cities500.zip'
ARCHIVE_MEMBER = 'cities500.txt'
REFRESH_INTERVAL = datetime.timedelta(days=7)
SCHEMA_VERSION = '1'

logger = logging.getLogger(__name__)
_refresh_lock = threading.Lock()
_separators = re.compile(r'[^\w]+', re.UNICODE)
_country_aliases = {'UK': 'GB', 'USA': 'US'}


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
    normalized, qualifier = _query_parts(query)
    if not normalized:
        return None
    with sqlite3.connect(path) as connection:
        place = _find(connection, normalized, qualifier)
        if place is None and ',' in query and qualifier is None:
            place = _find(connection, normalize_name(query.split(',', maxsplit=1)[0]), None)
        return place


def _query_parts(query: str) -> tuple[str, str | None]:
    stripped = query.strip()
    comma_parts = [part.strip() for part in stripped.split(',') if part.strip()]
    if len(comma_parts) > 1 and re.fullmatch(r'[A-Za-z]{2,3}', comma_parts[-1]):
        return normalize_name(comma_parts[0]), _country_aliases.get(comma_parts[-1].upper(), comma_parts[-1].upper())
    words = stripped.split()
    if len(words) > 1 and words[-1].isupper() and re.fullmatch(r'[A-Z]{2,3}', words[-1]):
        return normalize_name(' '.join(words[:-1])), _country_aliases.get(words[-1].upper(), words[-1].upper())
    return normalize_name(stripped), None


def _find(connection: sqlite3.Connection, normalized: str, qualifier: str | None) -> Place | None:
    qualifier_clause = ''
    parameters: list[str] = [normalized]
    if qualifier:
        qualifier_clause = 'AND (p.country_code = ? OR p.admin1_code = ?)'
        parameters.extend([qualifier, qualifier])
    row = connection.execute(
        f'''
            SELECT p.name, p.country_code, p.admin1_code, p.timezone
              FROM place_name AS n
              JOIN place AS p ON p.geoname_id = n.place_id
             WHERE n.normalized_name = ? {qualifier_clause}
             ORDER BY n.priority,
                      CASE p.feature_code WHEN 'PPLC' THEN 0 WHEN 'PPLA' THEN 1 WHEN 'PPLA2' THEN 2 ELSE 3 END,
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
        with sqlite3.connect(path) as connection:
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
            database = temporary_directory / 'cities500.sqlite'
            logger.info('Downloading GeoNames cities500 from %s.', DOWNLOAD_URL)
            with requests.get(DOWNLOAD_URL, headers={'User-Agent': USER_AGENT}, stream=True, timeout=(10, 120)) as response:
                response.raise_for_status()
                with archive_path.open('wb') as output:
                    for chunk in response.iter_content(1024 * 1024):
                        output.write(chunk)
            _build_database(archive_path, database)
            os.replace(database, path)
    except (OSError, requests.RequestException, sqlite3.Error, UnicodeError, ValueError, zipfile.BadZipFile) as error:
        raise FetchException(f'Unable to update the GeoNames cities500 database: {error}') from error


def _build_database(archive_path: Path, database: Path) -> None:
    count = 0
    with sqlite3.connect(database) as connection:
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
