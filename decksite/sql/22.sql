-- Speed up "cards uniquely played" query.
ALTER TABLE deck_card ADD INDEX idx_card (card);
