from magic import multiverse, rotation
from magic.database import db


def test_base_query_legalities() -> None:
    sql = multiverse.base_query("f.name = 'Mother of Runes'")
    db().execute('SET group_concat_max_len=100000')
    rs = db().select(sql)
    assert len(rs) == 1
    legalities = rs[0]['legalities']
    assert 'Penny Dreadful EMN:Legal' in legalities
    assert 'Penny Dreadful AKH:Legal' not in legalities

def test_seasons_enum_uptodate() -> None:
    """If this is failing, go append new set codes to rotation.SEASONS.
       This needs to be done every few months.

       This test is purely for futureproofing, and failing it does not mean anything is currently broken"""
    if rotation.next_rotation_ex()['code'] == '???':
        return
    assert rotation.next_rotation_ex()['code'] in rotation.SEASONS

def test_supertypes() -> None:
    assert multiverse.supertypes('Legendary Enchantment Creature - God') == ['Legendary']
    assert multiverse.supertypes('Artifact Creature - Construct') == []
    assert multiverse.supertypes('Snow Basic Land - Island') == ['Basic', 'Snow']
    assert multiverse.supertypes('Enchantment') == []
    assert multiverse.supertypes('Creature - Elder Dragon') == []

def test_subtypes() -> None:
    assert multiverse.subtypes('Legendary Enchantment Creature - God') == ['God']
    assert multiverse.subtypes('Artifact Creature - Construct') == ['Construct']
    assert multiverse.subtypes('Snow Basic Land - Island') == ['Island']
    assert multiverse.subtypes('Enchantment') == []
    assert multiverse.subtypes('Creature - Elder Dragon') == ['Elder', 'Dragon']
