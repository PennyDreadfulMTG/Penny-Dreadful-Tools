-- Speed up queries by using the right data type for discord_id
ALTER TABLE person CHANGE COLUMN discord_id discord_id BIGINT;
