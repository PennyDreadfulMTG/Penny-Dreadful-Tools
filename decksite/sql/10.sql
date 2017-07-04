CREATE TABLE deck_cache (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    deck_id INTEGER NOT NULL UNIQUE,
    colors TEXT,
    colored_symbols TEXT,
    legal_formats TEXT,
    FOREIGN KEY (deck_id) REFERENCES deck (id) ON UPDATE CASCADE ON DELETE CASCADE
);
