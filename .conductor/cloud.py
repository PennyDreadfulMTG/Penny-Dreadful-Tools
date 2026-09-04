"""Prepare an isolated, disposable MariaDB for Conductor cloud previews.

Uses the system Python so database restoration does not import the application.
The slow build-snapshot command is for CI/manual preparation, never workspace setup.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / '.context' / 'pd-cloud'
SOCKET = Path(tempfile.gettempdir()) / f'pd-cloud-{hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]}.sock'
PORT = 3307
PASSWORD = 'pd-cloud-dev'
REPO = 'PennyDreadfulMTG/Penny-Dreadful-Tools'
TAG = 'dev-db-snapshot'
ASSET = 'pd-cloud-db.tar.zst'
DATABASES = ('decksite', 'cards', 'prices', 'pdlogs', 'decksite_test')


def log(message: str) -> None:
    sys.stdout.write(f'[pd-cloud] {message}\n')
    sys.stdout.flush()


def run(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(args, check=True, **kwargs)


def version() -> str:
    output = subprocess.check_output(['mariadbd', '--version'], text=True)
    match = re.search(r'(\d+\.\d+)\.\d+', output)
    if not match:
        raise RuntimeError(f'Cannot identify MariaDB version: {output}')
    return match[1]


def validate_manifest(manifest: dict[str, Any]) -> None:
    expected = {'format': 1, 'mariadb': version(), 'architecture': platform.machine()}
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise RuntimeError(f'Snapshot {key}={manifest.get(key)!r}; this machine requires {value!r}. Rebuild the snapshot with matching MariaDB.')


def sql(statement: str) -> str:
    return subprocess.check_output([
        'mariadb', '--no-defaults', f'--socket={SOCKET}', '--user=root',
        '--batch', '--skip-column-names', '-e', statement,
    ], text=True).strip()


def running() -> bool:
    return subprocess.run([
        'mariadb-admin', '--no-defaults', f'--socket={SOCKET}', '--user=root', 'ping',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def start() -> None:
    if running():
        return
    log(f'Starting workspace MariaDB on 127.0.0.1:{PORT}')
    with (STATE / 'mariadb.log').open('a') as output:
        subprocess.Popen([
            'mariadbd', '--no-defaults', f'--datadir={STATE / "mysql"}',
            f'--socket={SOCKET}', f'--pid-file={STATE / "mariadb.pid"}',
            '--bind-address=127.0.0.1', f'--port={PORT}',
            '--innodb-buffer-pool-size=2G', '--innodb-flush-log-at-trx-commit=2',
            '--max-allowed-packet=1G', '--skip-log-bin', '--performance-schema=OFF',
        ], stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        if running():
            return
        time.sleep(0.5)
    raise RuntimeError(f'MariaDB did not start. See {STATE / "mariadb.log"}')


def stop() -> None:
    run('mariadb-admin', '--no-defaults', f'--socket={SOCKET}', '--user=root', 'shutdown')
    for _ in range(120):
        if not (STATE / 'mariadb.pid').exists():
            return
        time.sleep(0.5)
    raise RuntimeError('MariaDB did not shut down cleanly; refusing to snapshot it.')


def configure() -> None:
    path = ROOT / 'config.json'
    config = json.loads(path.read_text()) if path.exists() else {}
    config.update({
        'mysql_host': '127.0.0.1', 'mysql_port': PORT,
        'mysql_user': 'pennydreadful', 'mysql_passwd': PASSWORD,
        'decksite_database': 'decksite', 'magic_database': 'cards',
        'prices_database': 'prices', 'logsite_database': 'pdlogs',
        'decksite_test_database': 'decksite_test',
        'whoosh_index_dir': str(STATE / 'whoosh_index'),
        'typeahead_data_path': str(STATE / 'typeahead.json'),
        'production': False, 'create_github_issues': False, 'redis_enabled': False,
        'sentry_token': None, 'flask_server_name': None, 'flask_cookie_domain': None,
    })
    if not config.get('oauth2_client_secret'):
        config['oauth2_client_secret'] = secrets.token_hex(32)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config, indent=4, sort_keys=True) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def verify() -> None:
    # Verify actual data as the app user, not merely that the root socket responds.
    output = subprocess.check_output([
        'mariadb', '--no-defaults', '--host=127.0.0.1', f'--port={PORT}',
        '--user=pennydreadful', '--batch', '--skip-column-names', '-e',
        'SELECT EXISTS(SELECT 1 FROM decksite.deck); SELECT EXISTS(SELECT 1 FROM cards.card); '
        'SELECT EXISTS(SELECT 1 FROM decksite._arch_day_stats);',
    ], env={**os.environ, 'MYSQL_PWD': PASSWORD}, text=True)
    if output.split() != ['1', '1', '1']:
        raise RuntimeError('Snapshot is missing deck, card, or homepage summary data.')
    if not list((STATE / 'whoosh_index').glob('*.toc')):
        raise RuntimeError('Snapshot is missing its Whoosh search index.')
    if not (STATE / 'typeahead.json').is_file() or not (STATE / 'symbols.woff2').is_file():
        raise RuntimeError('Snapshot is missing search suggestions or the symbols font.')


def restore() -> None:
    if STATE.exists():
        raise RuntimeError(f'{STATE} exists but has no completed manifest. Inspect it before moving it aside and retrying; no data has been overwritten.')
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pd-restore-', dir=STATE.parent) as temporary:
        download = Path(temporary)
        source = os.environ.get('PD_CLOUD_SNAPSHOT_DIR')
        if source:
            for name in (ASSET, 'manifest.json', 'SHA256SUMS'):
                shutil.copyfile(Path(source) / name, download / name)
        else:
            log('Downloading prepared database snapshot from GitHub')
            run('gh', 'release', 'download', TAG, '--repo', REPO, '--dir', str(download),
                '--pattern', ASSET, '--pattern', 'manifest.json', '--pattern', 'SHA256SUMS')
        run('sha256sum', '--check', 'SHA256SUMS', cwd=download)
        validate_manifest(json.loads((download / 'manifest.json').read_text()))
        log('Restoring database and search index')
        unpacked = download / 'unpacked'
        unpacked.mkdir()
        run('tar', '--zstd', '--extract', '--file', str(download / ASSET),
            '--directory', str(unpacked), '--no-same-owner')
        shutil.copyfile(download / 'manifest.json', unpacked / 'manifest.json')
        unpacked.rename(STATE)


def setup() -> None:
    started = time.monotonic()
    if not (STATE / 'manifest.json').exists():
        restore()
    validate_manifest(json.loads((STATE / 'manifest.json').read_text()))
    start()
    verify()
    configure()
    fonts = ROOT / 'shared_web' / 'static' / 'fonts'
    fonts.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STATE / 'symbols.woff2', fonts / 'symbols.woff2')
    log(f'Database ready in {time.monotonic() - started:.1f}s')


def build_snapshot(output: Path) -> None:
    if STATE.exists():
        raise RuntimeError(f'Build requires a fresh {STATE}; existing data is never replaced.')
    STATE.mkdir(parents=True)
    run('mariadb-install-db', '--no-defaults', f'--datadir={STATE / "mysql"}',
        '--auth-root-authentication-method=normal', '--skip-test-db')
    start()
    try:
        for database in DATABASES:
            sql(f'CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        sql(f"CREATE USER 'pennydreadful'@'127.0.0.1' IDENTIFIED BY '{PASSWORD}'")
        for database in DATABASES:
            sql(f"GRANT ALL ON `{database}`.* TO 'pennydreadful'@'127.0.0.1'")
        configure()
        dump = STATE / 'dev-db.sql.gz'
        source = os.environ.get('PD_DEV_SQL')
        if source:
            shutil.copyfile(source, dump)
        else:
            run('curl', '--fail', '--location', '--retry', '3', '--output', str(dump),
                'https://pennydreadfulmagic.com/static/dev-db.sql.gz')
        log('Importing sanitized SQL (one-time snapshot build; takes several minutes)')
        with subprocess.Popen(['gzip', '-dc', str(dump)], stdout=subprocess.PIPE) as decompressor:
            run('mariadb', '--no-defaults', f'--socket={SOCKET}', '--user=root',
                '--max-allowed-packet=1G', 'decksite', stdin=decompressor.stdout)
            assert decompressor.stdout is not None
            decompressor.stdout.close()
            if decompressor.wait() != 0:
                raise RuntimeError('SQL decompression failed')
        dump.unlink()
        log('Building card database and search index')
        run('uv', 'run', '--frozen', 'python', 'run.py', 'init-cards')
        build_derived_assets()
        verify()
    finally:
        stop()
    pack_snapshot(output)


def build_derived_assets() -> None:
    # This table is absent from the sanitized SQL dump. Without it the first
    # homepage request triggers a full (slow) archetype preaggregation.
    run('uv', 'run', '--frozen', 'python', '-c',
        'from decksite.data import archetype; archetype.preaggregate_archetype_days()')
    run('uv', 'run', '--frozen', 'python', '-c',
        'from decksite import main; from maintenance import typeahead; '
        'ctx = main.APP.test_request_context(); ctx.push(); typeahead.run(); ctx.pop()')
    run('uv', 'run', '--frozen', 'python', '-c',
        'from magic import oracle; oracle.init(); from maintenance import fonts; fonts.ad_hoc()')
    shutil.copyfile(ROOT / 'shared_web/static/fonts/symbols.woff2', STATE / 'symbols.woff2')
    check_pages()


def check_pages() -> None:
    run('uv', 'run', '--frozen', 'python', '-c',
        'from decksite import main; client = main.APP.test_client(); '
        'paths = ["/", "/decks/", "/cards/", "/api/search/?q=bolt"]; '
        'results = [(path, client.get(path).status_code) for path in paths]; '
        'assert all(status == 200 for _, status in results), results')


def pack_snapshot(output: Path) -> None:
    if running():
        raise RuntimeError('Stop MariaDB cleanly before creating a snapshot.')
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'format': 1, 'mariadb': version(), 'architecture': platform.machine(),
                'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    log('Compressing cleanly stopped database')
    run('tar', '-I', 'zstd -T0 -3', '-cf', str(output / ASSET), '-C', str(STATE),
        'mysql', 'whoosh_index', 'typeahead.json', 'symbols.woff2')
    with (output / 'SHA256SUMS').open('w') as sums:
        run('sha256sum', ASSET, 'manifest.json', cwd=output, stdout=sums)
    shutil.copyfile(output / 'manifest.json', STATE / 'manifest.json')
    log(f'Snapshot ready: {output}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'start', 'build-snapshot'])
    parser.add_argument('--output', type=Path, default=ROOT / '.context' / 'pd-cloud-artifacts')
    args = parser.parse_args()
    if platform.system() != 'Linux' or (args.command != 'build-snapshot' and os.environ.get('CONDUCTOR_IS_LOCAL') != '0'):
        parser.error('Cloud commands require CONDUCTOR_IS_LOCAL=0 on Linux; macOS uses its existing services.')
    os.chdir(ROOT)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with (STATE.parent / 'pd-cloud.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Another cloud database setup is running; wait for it to finish.')
        if args.command == 'build-snapshot':
            build_snapshot(args.output.resolve())
        else:
            setup()


if __name__ == '__main__':
    main()
