-- Add column for MTGO match ID.
ALTER TABLE `match` ADD COLUMN `mtgo_id` INT(13) NULL;
