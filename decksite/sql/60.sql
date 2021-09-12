ALTER TABLE deck_cache ADD COLUMN season_id INT;
UPDATE
    deck_cache
INNER JOIN
    deck AS d ON deck_cache.deck_id = d.id
LEFT JOIN
    (
        SELECT
            `start`.id,
            `start`.code,
            `start`.start_date AS start_date,
            `end`.start_date AS end_date
        FROM
            season AS `start`
        LEFT JOIN
            season AS `end` ON `end`.id = `start`.id + 1
    ) AS season ON season.start_date <= d.created_date AND (season.end_date IS NULL OR season.end_date > d.created_date)
SET
    deck_cache.season_id = season.id;
ALTER TABLE deck_cache CHANGE COLUMN season_id season_id INT NOT NULL;
ALTER TABLE deck_cache ADD FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE;
