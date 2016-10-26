CREATE TABLE decks (
    id INTEGER PRIMARY KEY,
    last_retrieved INT,

    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    user TEXT NOT NULL,
    user_display TEXT NOT NULL,
    url TEXT NOT NULL,
    resource_uri TEXT NOT NULL,
    
    featured_card TEXT,
    date_updated INT,
    score INT,
    thumbnail_url TEXT,
    small_thumbnail_url TEXT
)