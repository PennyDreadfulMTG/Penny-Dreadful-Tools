CREATE TABLE IF NOT EXISTS competition_flag (
    id INT NOT NULL PRIMARY KEY,
    name VARCHAR(190) NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

INSERT INTO competition_flag (id, name) VALUES (1, 'Season Championship'), (2, 'Season Kick Off'), (3, 'The Penny Dreadful 500');

ALTER TABLE competition ADD COLUMN competition_flag_id INT REFERENCES competition_flag(id) ON UPDATE CASCADE ON DELETE CASCADE;

UPDATE competition SET competition_flag_id = 1 WHERE name LIKE '%%Champions%%';
UPDATE competition SET competition_flag_id = 2 WHERE name LIKE '%%ick%%ff%%' AND name NOT LIKE 'Penny Paradise%%';
UPDATE competition SET competition_flag_id = 3 WHERE name LIKE '%%500%%';
