ALTER TABLE deck ADD COLUMN decklist_hash CHAR(40);
CREATE INDEX deck_hash ON deck (decklist_hash);
