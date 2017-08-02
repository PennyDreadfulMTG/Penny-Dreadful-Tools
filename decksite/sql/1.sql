-- A person is a single human being.
-- We may end up double or treble logging people from different sources but the goal is one entry per unique human.
-- Site usernames are our most useful proxy for 'unique human'.
CREATE TABLE IF NOT EXISTS person (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name TEXT,
    tappedout_username VARCHAR(50) UNIQUE,
    mtgo_username VARCHAR(50) UNIQUE
);

-- The source of a deck. Tapped Out, Manual Entry, Gatherling, etc.
CREATE TABLE IF NOT EXISTS source (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) UNIQUE NOT NULL
);

INSERT INTO source (name) VALUES ('Tapped Out');
INSERT INTO source (name) VALUES ('Gatherling');

-- A deck in the wild. Used or published by a particular person on a particular date at a particular place.
-- If the same person enters the same 75 into several different competitions there will be several entries in this table.
CREATE TABLE IF NOT EXISTS deck (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    person_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    identifier VARCHAR(190) NOT NULL,
    name TEXT NOT NULL,
    created_date INTEGER NOT NULL,
    updated_date INTEGER NOT NULL,
    competition_id INTEGER,
    url TEXT,
    archetype_id INT,
    resource_uri TEXT,
    featured_card TEXT,
    score INT,
    thumbnail_url TEXT,
    small_thumbnail_url TEXT,
    wins INTEGER,
    losses INTEGER,
    finish INTEGER,
    FOREIGN KEY(person_id) REFERENCES person(id),
    FOREIGN KEY(source_id) REFERENCES source(id),
    CONSTRAINT deck_source_id_identifier UNIQUE (source_id, identifier)
);

-- Mapping between deck and the cards it contains.
CREATE TABLE IF NOT EXISTS deck_card (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    deck_id INTEGER NOT NULL,
    card VARCHAR(100) NOT NULL,
    n INTEGER NOT NULL,
    sideboard INTEGER NOT NULL,
    FOREIGN KEY(deck_id) REFERENCES deck(id),
    CONSTRAINT deck_card_deck_id_card_sideboard UNIQUE (deck_id, card, sideboard)
);

-- Types for competitions. 'League', 'Gatherling Thursdays', etc.
CREATE TABLE IF NOT EXISTS competition_type (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE
);

INSERT INTO competition_type (name) VALUES ('League'), ('Gatherling');

-- A specific competition. A particular league month or Gatherling tournament.
CREATE TABLE IF NOT EXISTS competition (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    start_date INTEGER NOT NULL,
    end_date INTEGER NOT NULL,
    name TEXT NOT NULL,
    competition_type_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    FOREIGN KEY(competition_type_id) REFERENCES competition_type(id)
);

ALTER TABLE deck ADD CONSTRAINT FOREIGN KEY(competition_id) REFERENCES competition(id);

-- Broad archetypes to slot decks into.
CREATE TABLE IF NOT EXISTS archetype (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name TEXT NOT NULL
);
ALTER TABLE deck ADD CONSTRAINT FOREIGN KEY(archetype_id) REFERENCES archetype(id);
-- Populate archetype
INSERT INTO archetype (name) VALUES ('Aggro'), ('Combo'), ('Control'), ('Aggro-Combo'), ('Aggro-Control'), ('Combo-Control'), ('Midrange'), ('Ramp'), ('Unclassified');
