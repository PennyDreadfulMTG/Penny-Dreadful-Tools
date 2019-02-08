-- Update this column to be the same width as all other card columns.
ALTER TABLE deck_card CHANGE COLUMN card card NVARCHAR(190);
