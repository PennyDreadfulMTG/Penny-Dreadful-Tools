-- name is a TEXT field so make normalized_name a TEXT field for when/if we get names >190 bytes.
ALTER TABLE deck_cache CHANGE COLUMN normalized_name normalized_name TEXT;
