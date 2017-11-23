-- Speed up cards query with covering index for subquery.
ALTER TABLE deck_card ADD INDEX idx_card_deck_id_sideboard_n (card, deck_id, sideboard, n);
