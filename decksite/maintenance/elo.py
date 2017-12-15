
from decksite.database import db

# Elo values from http://www.mtgeloproject.net/faq.php.
PEOPLE = {}
STARTING_ELO = 1500
ELO_WIDTH = 1600
K_FACTOR = 12

def ad_hoc():
    sql = """
    SELECT
        GROUP_CONCAT(d.person_id) AS people,
        GROUP_CONCAT(dm.games) AS games
    FROM `match` AS m
    INNER JOIN deck_match AS dm ON dm.match_id = m.id
    INNER JOIN deck AS d ON dm.deck_id = d.id
    GROUP BY m.id
    ORDER BY m.date, `round`
    """
    matches = db().execute(sql)
    for m in matches:
        match(m)
    for p in sorted(PEOPLE.items(), key=lambda x: -x[1]):
        print(p)

def match(m):
    if ',' not in m['games']:
        return
    elif int(m['games'].split(',')[0]) == 2:
        winner = m['people'].split(',')[0]
        loser = m['people'].split(',')[1]
    elif int(m['games'].split(',')[1]) == 2:
        winner = m['people'].split(',')[1]
        loser = m['people'].split(',')[0]
    else:
        return
    adjust(winner, loser)

def adjust(winner, loser):
    e = expected(elo(winner), elo(loser))
    change = K_FACTOR * (1 - e)
    PEOPLE[winner] = elo(winner) + change
    PEOPLE[loser] = elo(loser) - change

def expected(p1, p2):
    return 1.0 / (1 + 10**((p2 - p1) / ELO_WIDTH))

def elo(person):
    return PEOPLE.get(person, STARTING_ELO)
