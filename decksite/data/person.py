from munch import Munch

from magic import rotation
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

        COUNT(d.id) AS num_decks,
        SUM(d.wins) AS wins,
        SUM(d.losses) AS losses,
        SUM(d.draws) AS draws,
        ROUND((SUM(d.wins) / SUM(d.wins + d.losses)) * 100, 1) AS win_percent,
        SUM(CASE WHEN d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS num_competitions,

        SUM(CASE WHEN d.created_date >= %s THEN 1 ELSE 0 END) AS num_decks_season,
        SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) AS wins_season,
        SUM(CASE WHEN d.created_date >= %s THEN losses ELSE 0 END) AS losses_season,
        SUM(CASE WHEN d.created_date >= %s THEN draws ELSE 0 END) AS draws_season,
        ROUND((SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END + CASE WHEN d.created_date >= %s THEN losses ELSE 0 END)) * 100, 1) AS win_percent_season,
        SUM(CASE WHEN d.created_date >= %s AND d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS num_competitions_season

        FROM person AS p
        LEFT JOIN deck AS d ON p.id = d.person_id
        WHERE {where_clause}
        GROUP BY p.id
        ORDER BY num_decks_season DESC, num_decks DESC, name
    """.format(person_query=query.person_query(), where_clause=where_clause)
    people = [Person(r) for r in db().execute(sql, [rotation.last_rotation().timestamp()] * 8)]
    if len(people) > 0:
        set_decks(people)
    return people

def set_decks(people):
    people_by_id = {person.id: person for person in people}
    where_clause = 'person_id IN ({ids})'.format(ids=', '.join(str(k) for k in people_by_id.keys()))
    decks = deck.load_decks(where_clause)
    for p in people:
        p.decks = []
    for d in decks:
        people_by_id[d.person_id].decks.append(d)

class Person(Munch):
    pass
