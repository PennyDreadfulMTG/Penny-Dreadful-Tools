-- Sponsor is not set up correctly as a foreign key and has somehow got out of whack.
UPDATE sponsor SET id = 2 WHERE id = 5;
UPDATE sponsor SET id = 3 WHERE id = 6;
ALTER TABLE competition_series ADD FOREIGN KEY(sponsor_id) REFERENCES sponsor(id) ON UPDATE CASCADE ON DELETE CASCADE;
