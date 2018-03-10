CREATE TABLE IF NOT EXISTS sponsor (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(190) UNIQUE NOT NULL,
    url VARCHAR(190) UNIQUE
);

INSERT INTO sponsor (name, url) VALUES ('Cardhoarder', 'https://www.cardhoarder.com/'); # 1
INSERT INTO sponsor (name, url) VALUES ('Manatraders', 'https://www.manatraders.com/'); # 2
INSERT INTO sponsor (name, url) VALUES ('MTGO Traders', 'https://www.mtgotraders.com/'); # 3

ALTER TABLE competition_series ADD COLUMN sponsor_id INT;

UPDATE competition_series SET sponsor_id = 3 WHERE name = 'League';
UPDATE competition_series SET sponsor_id = 1 WHERE name = 'Penny Dreadful Thursdays' OR name = 'Penny Dreadful Saturdays' OR name = 'Penny Dreadful Sundays' OR name = 'Penny Dreadful Mondays';
UPDATE competition_series SET sponsor_id = 2 WHERE name = 'Penny Paradise';

INSERT INTO competition_series (name, competition_type_id, sponsor_id) VALUES ('APAC Penny Dreadful Sundays', 2, NULL); # 7

UPDATE competition SET competition_series_id = 7 WHERE name LIKE '%APAC%';
