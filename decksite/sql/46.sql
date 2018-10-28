CREATE TABLE IF NOT EXISTS confidence (
    deck_id INTEGER PRIMARY KEY UNIQUE,
    score INTEGER,
    FOREIGN KEY(deck_id) REFERENCES deck(id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- Clear existing predictions so that we recalculate a confidence score for them
UPDATE deck SET archetype_id = NULL WHERE reviewed = FALSE;
