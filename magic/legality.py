from magic import oracle
from magic.database import db

LEGAL_CARDS = dict()

def legal_deck(cards, format_id=None):
    legal = legality(cards, format_id)
    for c in legal:
        if not legal[c]:
            return False
    return True

# Does not check for 4-ofs nor 1 max restricted, yet.
def deck_legalities(cards):
    legal_in = []
    print("get legalities")
    for r in db().execute("SELECT name, id FROM format"):
        format_name = r['name']
        format_id = r['id']
        if " Block" in format_name:
            continue
        print("getting {}".format(format_name))
        if legal_deck(cards, format_id):
            legal_in.append(format_name)
    return legal_in


def legality(cards, format_id=None):
    if format_id is None:
        format_id = oracle.get_format_id('Penny Dreadful')
    l = {}
    cs = LEGAL_CARDS.get(format_id)
    if cs is None:
        sql = "{base_select} HAVING id IN (SELECT card_id FROM card_legality WHERE format_id = ? AND legality <> 'Banned')".format(base_select=oracle.base_query())
        cs = [r['name'] for r in db().execute(sql, [format_id])]
        LEGAL_CARDS[format_id] = cs
    for c in cards:
        l[c.id] = c.name in cs
    return l
