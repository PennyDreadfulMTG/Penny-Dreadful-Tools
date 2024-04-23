CREATE TABLE rotation_runs (
    number TINYINT UNSIGNED NOT NULL,
    name VARCHAR(190),
    season_id INT NOT NULL, -- Can't be a foreign key because season table won't next season when we want to use it
    PRIMARY KEY (number, name, season_id),
    INDEX idx_name (name),
    INDEX idx_season_id (season_id)
);
