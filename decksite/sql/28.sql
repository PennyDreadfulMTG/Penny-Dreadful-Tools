BEGIN;

CREATE TABLE IF NOT EXISTS competition_series (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(190) UNIQUE NOT NULL,
    competition_type_id INT NOT NULL,
    FOREIGN KEY (competition_type_id) REFERENCES competition_type (id)
);

INSERT INTO competition_series (name, competition_type_id) VALUES
    ('League', 1),
    ('Penny Dreadful Thursdays', 2),
    ('Penny Paradise', 2),
    ('Penny Dreadful Sundays', 2),
    ('Penny Dreadful Mondays', 2),
    ('Penny Dreadful Saturdays', 2);

ALTER TABLE competition ADD COLUMN competition_series_id INT;

UPDATE competition SET competition_series_id = 1 WHERE name LIKE '%%League%%';
UPDATE competition SET competition_series_id = 2 WHERE name LIKE '%%Thursday%%' OR name LIKE '%%PDT%%';
UPDATE competition SET competition_series_id = 3 WHERE name LIKE '%%Paradise%%';
UPDATE competition SET competition_series_id = 4 WHERE name LIKE '%%Sunday%%';
UPDATE competition SET competition_series_id = 5 WHERE name LIKE '%%Monday%%';
UPDATE competition SET competition_series_id = 6 WHERE name LIKE '%%Saturday%%';

ALTER TABLE competition DROP FOREIGN KEY competition_ibfk_1;
ALTER TABLE competition DROP COLUMN competition_type_id; -- Now derivable from competition_series_id

ALTER TABLE competition CHANGE COLUMN competition_series_id competition_series_id INT NOT NULL;
ALTER TABLE competition ADD FOREIGN KEY (competition_series_id) REFERENCES competition_series (id) ON UPDATE CASCADE ON DELETE CASCADE;

COMMIT;
