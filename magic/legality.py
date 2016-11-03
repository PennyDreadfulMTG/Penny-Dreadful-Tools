from shared.pd_exception import InvalidArgumentException

from magic import oracle
from magic.database import db

LEGAL_CARDS = dict()

def legal_deck(cards, format_name='Penny Dreadful'):
    legal = legality(cards, format_name=format_name)
    for c in legal:
        if not legal[c]:
            return False
    return True

# Does not check for 4-ofs nor 1 max restricted, yet.
def deck_legalities(cards):
    legal_in = []
    for r in db().execute("SELECT name, id FROM format"):
        format_name = r['name']
        if " Block" in format_name:
            continue
        if format_name in ["Commander", "Singleton 100", "Prismatic"]:
            # Difficult deckbuilding requirements - Ignore them for now.
            continue
        if legal_deck(cards, format_name):
            legal_in.append(format_name)
    return legal_in


def legality(cards, format_name='Penny Dreadful'):
    if format_name is None:
        raise InvalidArgumentException('Got None when expecting a format name in legality.legality')
    format_id = oracle.get_format_id(format_name)
    l = {}
    cs = LEGAL_CARDS.get(format_id)
    if cs is None:
        print("Building legality list for {format_name}".format(format_name=format_name))
        sql = "{base_select} HAVING id IN (SELECT card_id FROM card_legality WHERE format_id = ? AND legality <> 'Banned')".format(base_select=oracle.base_query())
        cs = [r['name'] for r in db().execute(sql, [format_id])]
        LEGAL_CARDS[format_id] = cs
    for c in cards:
        l[c.id] = c.name in cs
    return l

def init():
    oracle.set_legal_cards()
    # Don't hardcode this!
    oracle.set_legal_cards(season="EMN")
    deck_legalities([])
