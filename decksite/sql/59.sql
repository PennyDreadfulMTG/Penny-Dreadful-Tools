UPDATE person SET elo = 1500 WHERE elo IS NULL;
ALTER TABLE person CHANGE COLUMN elo elo INT NOT NULL DEFAULT 1500;
UPDATE person SET elo = 1500 WHERE elo IS NULL;
