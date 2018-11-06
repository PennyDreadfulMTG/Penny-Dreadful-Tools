CREATE TABLE IF NOT EXISTS person_alias (
    canonical_id INT NOT NULL,
    alias_id INT NOT NULL,
    PRIMARY KEY (canonical_id, alias_id),
    FOREIGN KEY canonical_id REFERENCES person (id),
    FOREIGN KEY alias_id REFERENCES person (id)
);
