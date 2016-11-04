CREATE TABLE IF NOT EXISTS `match` (
    id INTEGER PRIMARY KEY,
    `date` INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS deck_match (
    id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL,
    deck_id INTEGER NOT NULL,
    games INTEGER NOT NULL,
    FOREIGN KEY(match_id) REFERENCES `match`(id),
    FOREIGN KEY(deck_id) REFERENCES deck(id)
);
