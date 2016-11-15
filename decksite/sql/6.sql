ALTER TABLE deck ADD COLUMN decklist_hash TEXT;
CREATE INDEX deck_hash ON deck (decklist_hash);
CREATE INDEX generate_name ON person (IFNULL(IFNULL(name, mtgo_username), tappedout_username));