-- Speed up "cards uniquely played" query.
ALTER TABLE deck_card DROP INDEX idx_card;
