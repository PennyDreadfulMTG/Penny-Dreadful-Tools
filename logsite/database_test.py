# type: ignore

from sqlalchemy import create_engine, text

from logsite import APP


def test_pool_replaces_a_connection_closed_by_the_database_server() -> None:
    engine = create_engine(APP.config['SQLALCHEMY_DATABASE_URI'], **APP.config['SQLALCHEMY_ENGINE_OPTIONS'])
    killer = create_engine(APP.config['SQLALCHEMY_DATABASE_URI'])
    try:
        with engine.connect() as connection:
            old_id = connection.scalar(text('SELECT CONNECTION_ID()'))
        with killer.connect() as connection:
            connection.execute(text(f'KILL CONNECTION {int(old_id)}'))
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT CONNECTION_ID()')) != old_id
            assert connection.scalar(text('SELECT 1')) == 1
    finally:
        engine.dispose()
        killer.dispose()
