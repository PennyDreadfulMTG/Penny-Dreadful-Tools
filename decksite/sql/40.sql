-- Denormalize wins/draws/losses to deck_cache for faster queries.
ALTER TABLE deck_cache ADD COLUMN wins INT NOT NULL DEFAULT 0;
ALTER TABLE deck_cache ADD COLUMN losses INT NOT NULL DEFAULT 0;
ALTER TABLE deck_cache ADD COLUMN draws INT NOT NULL DEFAULT 0;
ALTER TABLE deck_cache ADD COLUMN active_date INT NOT NULL;
UPDATE
    deck_cache AS dc
LEFT JOIN
    (
        SELECT
            d.id,
            IFNULL(SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END), 0) AS wins, -- IFNULL so we still count byes as wins.
            IFNULL(SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END), 0) AS losses,
            IFNULL(SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END), 0) AS draws,
            IFNULL(MAX(m.date), d.created_date) AS active_date
        FROM
            deck AS d
        LEFT JOIN
            deck_match AS dm ON dm.deck_id = d.id
        LEFT JOIN
            deck_match AS odm ON dm.match_id = odm.match_id AND dm.deck_id <> odm.deck_id
        LEFT JOIN
            `match` AS m ON m.id = dm.match_id
        GROUP BY
            d.id
    ) AS dsum ON dc.deck_id = dsum.id
SET
    dc.wins = dsum.wins,
    dc.draws = dsum.draws,
    dc.losses = dsum.losses,
    dc.active_date = dsum.active_date;
