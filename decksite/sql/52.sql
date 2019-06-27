-- Change deck_card so that each row has the number in main and side in that deck
-- instead of the old way (each row counts for main or side depending on column sideboard)

-- No table references deck_card, so we'll just delete it and make a new one
CREATE TABLE IF NOT EXISTS _new_deck_card (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    deck_id INTEGER NOT NULL,
    card VARCHAR(100) NOT NULL,
    n_main INTEGER NOT NULL,
    n_side INTEGER NOT NULL,
    FOREIGN KEY(deck_id) REFERENCES deck(id),
    CONSTRAINT deck_card_deck_id_card UNIQUE (deck_id, card)
    ) AS
    SELECT deck_id, card, 
           SUM(CASE WHEN sideboard=0 THEN n ELSE 0 END) as n_main, 
           SUM(CASE WHEN sideboard=1 THEN n ELSE 0 END) as n_side
    FROM deck_card
    GROUP BY card, deck_id
    ORDER BY deck_id;

RENAME TABLE deck_card to _old_deck_card;

RENAME TABLE _new_deck_card TO deck_card;

# Reset the preaggregation
DROP TABLE IF EXISTS _card_stats, _card_person_stats;
