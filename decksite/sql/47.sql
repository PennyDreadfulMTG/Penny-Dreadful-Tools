CREATE TABLE IF NOT EXISTS person_alias (
    person_id INT NOT NULL,
    alias NVARCHAR(190) NOT NULL,
    PRIMARY KEY (person_id, alias),
    FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
);
