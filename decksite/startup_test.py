import subprocess
import sys
import textwrap


def test_worker_startup_releases_database_connections_before_serving_requests() -> None:
    # A fresh interpreter exercises the real import order, including oracle and
    # migration initialization. Retain every connection so GC cannot hide a leak.
    script = textwrap.dedent('''\
        from shared import configuration, database

        connections = []
        connect = database.get_database

        def track_connection(name):
            db = connect(name)
            connections.append(db)
            return db

        database.get_database = track_connection
        from decksite import main
        from magic import oracle

        assert oracle.CARDS_BY_NAME
        assert {db.name for db in connections} >= {configuration.get_str('magic_database'), configuration.get_str('decksite_database')}
        assert all(not db.connection.open for db in connections), [db.name for db in connections if db.connection.open]
    ''')
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
