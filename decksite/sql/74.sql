ALTER TABLE rule_card ADD COLUMN sideboard BOOL;
UPDATE rule_card SET sideboard = FALSE;
