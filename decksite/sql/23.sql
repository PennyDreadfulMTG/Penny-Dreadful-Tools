-- Speed up rendering of long lists of decks.
ALTER TABLE deck_cache ADD COLUMN normalized_name VARCHAR(190);
