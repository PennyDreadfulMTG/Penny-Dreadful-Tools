-- Set DELETEs to CASCADE as they do on deck_cache. These records are meaningless without the deck.
ALTER TABLE deck_card DROP FOREIGN KEY deck_card_ibfk_1;
ALTER TABLE deck_card ADD FOREIGN KEY(deck_id) REFERENCES deck(id) ON UPDATE CASCADE ON DELETE CASCADE;
DELETE FROM deck WHERE wins = 0 AND losses = 0 AND draws = 0 AND retired;
