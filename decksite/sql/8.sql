# For each column:

ALTER TABLE
    archetype
    CHANGE name name
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    competition
    CHANGE name name
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    competition
    CHANGE url url
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    competition_type
    CHANGE name name
    VARCHAR(190)
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck
    CHANGE identifier identifier
    VARCHAR(190)
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck
    CHANGE name name
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck
    CHANGE url url
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck
    CHANGE resource_uri resource_uri
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck
    CHANGE featured_card featured_card
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck
    CHANGE thumbnail_url thumbnail_url
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck
    CHANGE small_thumbnail_url small_thumbnail_url
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck_card
    CHANGE card card
    VARCHAR(100)
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    person
    CHANGE name name
    TEXT
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    person
    CHANGE tappedout_username tappedout_username
    VARCHAR(50)
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    person
    CHANGE mtgo_username mtgo_username
    VARCHAR(50)
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    source
    CHANGE name name
    VARCHAR(50)
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;


# For each table:

ALTER TABLE
    archetype
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    competition
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    competition_type
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    db_version
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck_card
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    deck_match
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    `match`
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    person
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

ALTER TABLE
    source# For each column:
    CONVERT TO CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;


# For each database:
ALTER DATABASE
    decksite
    CHARACTER SET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;
