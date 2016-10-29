import os

from shared import configuration
from shared.database import Database
from shared.pd_exception import DatabaseException

def location():
    return '{scratch_dir}/tmp.db'.format(scratch_dir=configuration.get('scratch_dir'))

def setup():
    db = Database(location())
    db.execute('CREATE TABLE IF NOT EXISTS x (id INTEGER PRIMARY KEY, v TEXT)')
    return db

def teardown():
    try:
        os.remove(location())
    except FileNotFoundError:
        pass

def test_db():
    db = setup()
    db.execute("INSERT INTO x (v) VALUES ('A')")
    rs = db.execute('SELECT v FROM x')
    assert len(rs) == 1
    assert rs[0]['v'] == 'A'
    db = setup()
    rs = db.execute('SELECT v FROM x')
    assert len(rs) == 1
    assert rs[0]['v'] == 'A'
    teardown()

def test_transaction():
    db = setup()
    db.execute('BEGIN TRANSACTION')
    db.execute("INSERT INTO x (v) VALUES ('A')")
    rs = db.execute('SELECT v FROM x')
    assert len(rs) == 1
    assert rs[0]['v'] == 'A'
    db = setup()
    rs = db.execute('SELECT v FROM x')
    assert len(rs) == 0
    db.execute('BEGIN TRANSACTION')
    db.execute("INSERT INTO x (v) VALUES ('A')")
    rs = db.execute('SELECT v FROM x')
    assert len(rs) == 1
    assert rs[0]['v'] == 'A'
    db.execute('COMMIT')
    db = setup()
    rs = db.execute('SELECT v FROM x')
    assert len(rs) == 1
    assert rs[0]['v'] == 'A'
    teardown()

def test_value():
    db = setup()
    db.execute("INSERT INTO x (v) VALUES ('A'), ('B'), ('C')")
    assert db.value('SELECT id FROM x WHERE v = ?', ['B']) == 2
    teardown()
    db = setup()
    assert db.value('SELECT id FROM x WHERE v = 999', default='Z') == 'Z'
    exception_occurred = False
    try:
        db.value('SELECT id FROM x WHERE v = 999', fail_on_missing=True)
    except DatabaseException:
        exception_occurred = True
    assert exception_occurred
    teardown()

def test_values():
    db = setup()
    db.execute("INSERT INTO x (v) VALUES ('A'), ('B'), ('C')")
    assert db.values('SELECT id FROM x ORDER BY id') == [1, 2, 3]
    assert db.values('SELECT v FROM x ORDER BY id') == ['A', 'B', 'C']
    teardown()

def test_insert():
    db = setup()
    assert db.insert("INSERT INTO x (v) VALUES ('A')") == 1
    assert db.insert("INSERT INTO x (v) VALUES ('B')") == 2
    assert db.insert("INSERT INTO x (v) VALUES ('C')") == 3
    teardown()
