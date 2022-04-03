ALTER TABLE competition_series ADD COLUMN day_of_week SMALLINT;
UPDATE competition_series SET day_of_week = 1 WHERE name LIKE '%%FNM%%';
UPDATE competition_series SET day_of_week = 2 WHERE name LIKE '%%Saturday%%';
UPDATE competition_series SET day_of_week = 3 WHERE name LIKE '%%Sunday%%';
UPDATE competition_series SET day_of_week = 4 WHERE name LIKE '%%Monday%%';
UPDATE competition_series SET day_of_week = 5 WHERE name LIKE '%%Tuesday%%';
UPDATE competition_series SET day_of_week = 6 WHERE name LIKE '%%Wednesday%%';
UPDATE competition_series SET day_of_week = 7 WHERE name LIKE '%%Thursday%%';
