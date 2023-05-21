CREATE TABLE doorprize (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    competition_name TEXT NOT NULL UNIQUE,
    winner_name TEXT NOT NULL
)
