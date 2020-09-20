CREATE TABLE IF NOT EXISTS deck_game_played (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    deck_id INT NOT NULL,
    match_id INT NOT NULL,
    game_number INT NOT NULL,
    result INT NOT NULL,
    mulligans INT NOT NULL,
    FOREIGN KEY(deck_id) REFERENCES deck(id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS card_played (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    deck_game_played_id INT NOT NULL,
    game_number INT NOT NULL,
    card VARCHAR(100) NOT NULL,
    turn INT NOT NULL,
    FOREIGN KEY(deck_game_played_id) REFERENCES deck_game_played(id) ON UPDATE CASCADE ON DELETE CASCADE
);
