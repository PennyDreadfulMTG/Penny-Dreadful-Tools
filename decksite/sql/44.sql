-- Speed up deck.load_cards by giving it a covering index.
ALTER TABLE deck_card ADD INDEX idx_deck_id_card_n, sideboard (deck_id, card, n, sideboard);
