from decksite.data import deck, preaggregation, query
from decksite.database import db
from magic import oracle
from magic.models import Card
from shared import guarantee
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import retry_after_calling


def preaggregate() -> None:
    preaggregate_card()
    preaggregate_card_archetype()
    preaggregate_card_person()
    preaggregate_unique()
    preaggregate_trailblazer()


def preaggregate_card() -> None:
    table = '_card_stats'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            num_decks INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (season_id, name, deck_type),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            card AS name,
            season.season_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(dsum.wins), 0) AS wins,
            IFNULL(SUM(dsum.losses), 0) AS losses,
            IFNULL(SUM(dsum.draws), 0) AS draws,
            SUM(CASE WHEN dsum.wins >= 5 AND dsum.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
        FROM
            deck AS d
        INNER JOIN
            -- Eiliminate maindeck/sideboard double-counting with DISTINCT. See #5493.
            (SELECT DISTINCT card, deck_id FROM deck_card) AS dc ON d.id = dc.deck_id
        {query.competition_join()}
        {query.season_join()}
        {deck.nwdl_join()}
        GROUP BY
            card,
            season.season_id,
            ct.name
    """
    preaggregation.preaggregate(table, sql)


def preaggregate_card_archetype() -> None:
    table = '_card_archetype_stats'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            archetype_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (season_id, archetype_id, name, deck_type),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (archetype_id) REFERENCES archetype (id)  ON UPDATE CASCADE ON DELETE CASCADE,
            INDEX idx_archetype_id_name (archetype_id, name)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            card AS name,
            season.season_id,
            d.archetype_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(dsum.wins), 0) AS wins,
            IFNULL(SUM(dsum.losses), 0) AS losses,
            IFNULL(SUM(dsum.draws), 0) AS draws,
            SUM(CASE WHEN dsum.wins >= 5 AND dsum.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
        FROM
            deck AS d
        INNER JOIN
            -- Eliminate maindeck/sideboard double-counting with DISTINCT. See #5493.
            (SELECT DISTINCT card, deck_id FROM deck_card) AS dc ON d.id = dc.deck_id
        {query.competition_join()}
        {query.season_join()}
        {deck.nwdl_join()}
        WHERE
            d.archetype_id IS NOT NULL
        GROUP BY
            card,
            d.archetype_id,
            season.season_id,
            ct.name
    """
    preaggregation.preaggregate(table, sql)


def preaggregate_card_person() -> None:
    table = '_card_person_stats'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            name VARCHAR(190) NOT NULL,
            season_id INT NOT NULL,
            person_id INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            perfect_runs INT NOT NULL,
            tournament_wins INT NOT NULL,
            tournament_top8s INT NOT NULL,
            deck_type ENUM('league', 'tournament', 'other') NOT NULL,
            PRIMARY KEY (season_id, person_id, name, deck_type),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id)  ON UPDATE CASCADE ON DELETE CASCADE,
            INDEX idx_person_id_name (person_id, name)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            card AS name,
            season.season_id,
            d.person_id,
            SUM(CASE WHEN d.id IS NOT NULL THEN 1 ELSE 0 END) AS num_decks,
            IFNULL(SUM(dsum.wins), 0) AS wins,
            IFNULL(SUM(dsum.losses), 0) AS losses,
            IFNULL(SUM(dsum.draws), 0) AS draws,
            SUM(CASE WHEN dsum.wins >= 5 AND dsum.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN dsum.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN dsum.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            (CASE WHEN ct.name = 'League' THEN 'league' WHEN ct.name = 'Gatherling' THEN 'tournament' ELSE 'other' END) AS deck_type
        FROM
            deck AS d
        INNER JOIN
            -- Eliminate maindeck/sideboard double-counting with DISTINCT. See #5493.
            (SELECT DISTINCT card, deck_id FROM deck_card) AS dc ON d.id = dc.deck_id
        {query.competition_join()}
        {query.season_join()}
        {deck.nwdl_join()}
        GROUP BY
            card,
            d.person_id,
            season.season_id,
            ct.name
        ORDER BY
            NULL -- Tell the database that we don't need the results back in the GROUP BY order, any order will do.
    """
    preaggregation.preaggregate(table, sql)


def preaggregate_unique() -> None:
    table = '_unique_cards'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            card VARCHAR(100) NOT NULL,
            person_id INT NOT NULL,
            PRIMARY KEY (card, person_id),
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        )
        SELECT
            card,
            person_id
        FROM
            deck_card AS dc
        INNER JOIN
            deck AS d ON dc.deck_id = d.id
        WHERE
            d.id IN (SELECT deck_id FROM deck_match)
        GROUP BY
            card
        HAVING
            COUNT(DISTINCT person_id) = 1
    """
    preaggregation.preaggregate(table, sql)


def preaggregate_trailblazer() -> None:
    table = '_trailblazer_cards'
    sql = f"""
        CREATE TABLE IF NOT EXISTS _new{table} (
            card VARCHAR(100) NOT NULL,
            deck_id INT NOT NULL,
            PRIMARY KEY (card, deck_id),
            FOREIGN KEY (deck_id) REFERENCES deck (id) ON UPDATE CASCADE ON DELETE CASCADE
        )
        SELECT DISTINCT
            d.id AS deck_id,
            card,
            d.created_date AS `date`
        FROM
            deck AS d
        INNER JOIN
            deck_card AS dc ON dc.deck_id = d.id
        WHERE
            (dc.card, d.created_date) IN
                (
                    SELECT
                        card,
                        MIN(d.created_date)
                    FROM
                        deck_card AS dc
                    INNER JOIN
                        deck AS d ON dc.deck_id = d.id
                    INNER JOIN
                        deck_match AS dm ON dm.deck_id = d.id
                    {query.competition_join()}
                    WHERE
                        d.id IN (SELECT deck_id FROM deck_match GROUP BY deck_id HAVING COUNT(*) >= 1)
                    GROUP BY
                        card
                )
    """
    preaggregation.preaggregate(table, sql)


@retry_after_calling(preaggregate)
def load_cards(
    additional_where: str = 'TRUE',
    order_by: str = 'num_decks DESC, record, name',
    limit: str = '',
    archetype_id: int | None = None,
    person_id: int | None = None,
    season_id: int | None = None,
    tournament_only: bool = False,
    all_legal: bool = False,
) -> tuple[list[Card], int]:
    if person_id:
        table = '_card_person_stats'
        where = f'person_id = {sqlescape(person_id)}'
        group_by = 'person_id, cs.name'
    elif archetype_id:
        table = '_card_archetype_stats'
        where = f'archetype_id = {archetype_id}'
        group_by = 'archetype_id, cs.name'
    else:
        table = '_card_stats'
        where = 'TRUE'
        group_by = 'cs.name'
    if tournament_only:
        where = f"({where}) AND deck_type = 'tournament'"
    if all_legal:
        from_clause = f'_legal_cards AS cs LEFT JOIN {table} AS other ON cs.name = other.name AND cs.season_id = other.season_id'
    else:
        from_clause = f'{table} AS cs'
    season_query = query.season_query(season_id, 'cs.season_id')
    sql = f"""
        SELECT
            cs.name,
            SUM(IFNULL(num_decks, 0)) AS num_decks,
            SUM(IFNULL(wins, 0)) AS wins,
            SUM(IFNULL(losses, 0)) AS losses,
            SUM(IFNULL(draws, 0)) AS draws,
            SUM(IFNULL(wins, 0) - losses) AS record,
            SUM(IFNULL(perfect_runs, 0)) AS perfect_runs,
            SUM(IFNULL(tournament_wins, 0)) AS tournament_wins,
            SUM(IFNULL(tournament_top8s, 0)) AS tournament_top8s,
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS win_percent,
            COUNT(*) OVER () AS total
        FROM
            {from_clause}
        WHERE
            ({where}) AND ({additional_where}) AND ({season_query})
        GROUP BY
            {group_by}
        ORDER BY
            {order_by}
        {limit}
    """
    rs = db().select(sql)
    cs = [Container({k: v for k, v in r.items() if k != 'total'}) for r in rs]
    cards = oracle.cards_by_name()
    for c in cs:
        c.update(cards[c.name])
        c.played_competitively = c.wins or c.draws or c.losses
    return cs, 0 if not rs else rs[0]['total']


@retry_after_calling(preaggregate_card)
def load_card(name: str, tournament_only: bool = False, season_id: int | None = None) -> Card:
    cs, _ = load_cards(additional_where=f'name = {sqlescape(name)}', order_by='NULL', season_id=season_id, tournament_only=tournament_only)
    c = guarantee.at_most_one(cs)
    if c:
        return c
    # If there is no card in the db for this name-tournament_only-season_id combo we fake one to show as a placeholder
    c = Card(oracle.load_card(name), True)  # New Card, don't store these values in CARDS_BY_NAME copy
    c.num_decks = c.wins = c.losses = c.draws = c.record = c.tournament_wins = c.tournament_top8s = 0
    c.played_competitively = False
    c.win_percent = ''
    return c


@retry_after_calling(preaggregate_unique)
def unique_cards_played(person_id: int) -> list[str]:
    sql = """
        SELECT
            card
        FROM
            _unique_cards
        WHERE
            person_id = %s
    """
    return db().values(sql, [person_id])


@retry_after_calling(preaggregate_trailblazer)
def trailblazer_cards(person_id: int) -> list[str]:
    sql = """
        SELECT
            card
        FROM
            _trailblazer_cards AS tc
        INNER JOIN
            deck AS d ON tc.deck_id = d.id
        WHERE
            d.person_id = %s
    """
    return db().values(sql, [person_id])


def card_exists(name: str) -> bool:
    sql = 'SELECT EXISTS(SELECT * FROM deck_card WHERE card = %s LIMIT 1)'
    return bool(db().value(sql, [name]))
