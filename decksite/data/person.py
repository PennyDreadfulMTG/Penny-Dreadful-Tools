from magic import rotation
from shared.container import Container
from shared.database import sqlescape

from decksite.data import deck, guarantee, query
from decksite.database import db

def load_person(person_id):
    return guarantee.exactly_one(load_people('p.id = {id}'.format(id=sqlescape(person_id))))

def load_person_by_username(username):
    return guarantee.exactly_one(load_people('p.mtgo_username = {username}'.format(username=sqlescape(username))))

def load_people(where_clause='1 = 1'):
    sql = """
        SELECT p.id, {person_query} AS name,

        COUNT(d.id) AS `all.num_decks`,
        SUM(d.wins) AS `all.wins`,
        SUM(d.losses) AS `all.losses`,
        SUM(d.draws) AS `all.draws`,
        ROUND((SUM(d.wins) / SUM(d.wins + d.losses)) * 100, 1) AS `all.win_percent`,
        SUM(CASE WHEN d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS `all.num_competitions`,

        SUM(CASE WHEN d.created_date >= %s THEN 1 ELSE 0 END) AS `season.num_decks`,
        SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) AS `season.wins`,
        SUM(CASE WHEN d.created_date >= %s THEN losses ELSE 0 END) AS `season.losses`,
        SUM(CASE WHEN d.created_date >= %s THEN draws ELSE 0 END) AS `season.draws`,
        ROUND((SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END + CASE WHEN d.created_date >= %s THEN losses ELSE 0 END)) * 100, 1) AS `season.win_percent`,
        SUM(CASE WHEN d.created_date >= %s AND d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS `season.num_competitions`

        FROM person AS p
        LEFT JOIN deck AS d ON p.id = d.person_id
        WHERE {where_clause}
        GROUP BY p.id
        ORDER BY `season.num_decks` DESC, `all.num_decks` DESC, name
    """.format(person_query=query.person_query(), where_clause=where_clause)
    people = [Person(r) for r in db().execute(sql, [rotation.last_rotation().timestamp()] * 8)]
    if len(people) > 0:
        set_decks(people)
    return people

def set_decks(people):
    people_by_id = {person.id: person for person in people}
    where_clause = 'd.person_id IN ({ids})'.format(ids=', '.join(str(k) for k in people_by_id.keys()))
    decks = deck.load_decks(where_clause)
    for p in people:
        p.decks = []
    for d in decks:
        people_by_id[d.person_id].decks.append(d)

class Person(Container):
    pass
