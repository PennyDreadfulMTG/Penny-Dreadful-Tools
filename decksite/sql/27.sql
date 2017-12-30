ALTER TABLE person ADD COLUMN banned BOOLEAN NOT NULL DEFAULT 0;
UPDATE person SET banned = 1 WHERE mtgo_username = 'wooten22';
