CREATE TABLE IF NOT EXISTS season (
    id INT PRIMARY KEY AUTO_INCREMENT,
    `number` TINYINT NOT NULL UNIQUE,
    code VARCHAR(3) NOT NULL UNIQUE,
    start_date INT
);
INSERT INTO season (`number`, code, start_date) VALUES (1, 'EMN', 1469088000);
INSERT INTO season (`number`, code, start_date) VALUES (2, 'KLD', 1475222400);
INSERT INTO season (`number`, code, start_date) VALUES (3, 'AER', 1484899200);
INSERT INTO season (`number`, code, start_date) VALUES (4, 'AKH', 1493366400);
INSERT INTO season (`number`, code, start_date) VALUES (5, 'HOU', 1500019200);
INSERT INTO season (`number`, code, start_date) VALUES (6, 'XLN', 1506672000);
INSERT INTO season (`number`, code, start_date) VALUES (7, 'RIX', 1516348800);
