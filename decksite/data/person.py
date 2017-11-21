from magic import rotation
from shared.container import Container
from shared.database import sqlescape

from decksite.data import deck, guarantee, query
from decksite.database import db

def load_person(person):
    try:
        person_id = int(person)
        username = "'{person}'".format(person=person)
    except ValueError:
        person_id = 0
        username = sqlescape(person)
    return guarantee.exactly_one(load_people('p.id = {person_id} OR p.mtgo_username = {username}'.format(person_id=person_id, username=username)))

def load_people(where='1 = 1'):
    sql = """
        SELECT p.id, {person_query} AS name,

        COUNT(d.id) AS `all_num_decks`,
        SUM(d.wins) AS `all_wins`,
        SUM(d.losses) AS `all_losses`,
        SUM(d.draws) AS `all_draws`,
        IFNULL(ROUND((SUM(d.wins) / SUM(d.wins + d.losses)) * 100, 1), '') AS `all_win_percent`,
        SUM(CASE WHEN d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS `all_num_competitions`,

        SUM(CASE WHEN d.created_date >= %s THEN 1 ELSE 0 END) AS `season_num_decks`,
        SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) AS `season_wins`,
        SUM(CASE WHEN d.created_date >= %s THEN losses ELSE 0 END) AS `season_losses`,
        SUM(CASE WHEN d.created_date >= %s THEN draws ELSE 0 END) AS `season_draws`,
        IFNULL(ROUND((SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END + CASE WHEN d.created_date >= %s THEN losses ELSE 0 END)) * 100, 1), '') AS `season_win_percent`,
        SUM(CASE WHEN d.created_date >= %s AND d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS `season_num_competitions`

        FROM person AS p
        LEFT JOIN deck AS d ON p.id = d.person_id
        WHERE {where}
        GROUP BY p.id
        ORDER BY `season_num_decks` DESC, `all_num_decks` DESC, name
    """.format(person_query=query.person_query(), where=where)
    people = [Person(r) for r in db().execute(sql, [rotation.last_rotation().timestamp()] * 8)]
    if len(people) > 0:
        set_decks(people)
    return people

def set_decks(people):
    people_by_id = {person.id: person for person in people}
    where = 'd.person_id IN ({ids})'.format(ids=', '.join(str(k) for k in people_by_id.keys()))
    decks = deck.load_decks(where)
    for p in people:
        p.decks = []
    for d in decks:
        people_by_id[d.person_id].decks.append(d)

def associate(d, discord_id):
    person = guarantee.exactly_one(load_people('d.id = {deck_id}'.format(deck_id=sqlescape(d.id))))
    sql = 'UPDATE person SET discord_id = ? WHERE id = ?'
    return db().execute(sql, [discord_id, person.id])

class Person(Container):
    pass
