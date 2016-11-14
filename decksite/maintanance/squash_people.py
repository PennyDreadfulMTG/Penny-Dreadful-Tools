from decksite.data import guarantee, person
from decksite.database import db
from decksite.scrapers import tappedout

def run():
    partials = person.load_people('mtgo_username is NULL')

    for p in partials:
        source = p.decks[0].source_name
        tapped_username = p.name
        guess = person.load_people('LOWER(mtgo_username) = "{0}"'.format(tapped_username))
        print("{0}: {1}".format(tapped_username, len(guess)))
        if len(guess) == 0 and source == "Tapped Out":
            raw_data = tappedout.scrape_user(tapped_username)
            if raw_data['mtgo_username'] is not None:
                guess = person.load_people('LOWER(mtgo_username) = "{0}"'.format(raw_data['mtgo_username']))

        if len(guess) > 0:
            print(guess[0].name)
            squash(guarantee.exactly_one(guess), p)


def squash(old, new):
    assert old.id != new.id
    print("Squashing {new.name} ({new.id}) into {old.name} ({old.id})".format(old=old, new=new))
    sql = """
        BEGIN TRANSACTION;
        WITH 
            old as (
                SELECT * FROM person 
                WHERE id = {old.id}  
            ), 
            new as (
                SELECT * FROM person 
                WHERE id = {new.id}  
            )
            INSERT OR REPLACE INTO person (tappedout_username, mtgo_username)
                SELECT 
                    IFNULL(old.tappedout_username, new.tappedout_username) as tappedout_username,
                    IFNULL(old.mtgo_username, new.mtgo_username) as mtgo_username 
                FROM old JOIN new;
        UPDATE deck 
            SET person_id = last_insert_rowid() 
            WHERE person_id IN ({old.id}, {new.id});
        END TRANSACTION;
    """.format(new=new, old=old)
    db().execute(sql)
    return db().value('SELECT last_insert_rowid()')
