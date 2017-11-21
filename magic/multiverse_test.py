from magic import multiverse
from magic.database import db

def test_base_query_legalities():
    sql = multiverse.base_query("f.name = 'Mother of Runes'")
    rs = db().execute(sql)
    assert len(rs) == 1
    legalities = rs[0]['legalities']
    assert 'Penny Dreadful EMN:Legal' in legalities
    assert 'Penny Dreadful AKH:Legal' not in legalities
