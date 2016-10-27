CREATE TABLE decklists (
                id INTEGER PRIMARY KEY,
                deckid INT,
                name TEXT,
                count INT,
                FOREIGN KEY(deckid) REFERENCES decks(id)
            )