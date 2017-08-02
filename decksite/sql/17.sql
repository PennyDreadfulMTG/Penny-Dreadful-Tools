-- Prevent key-too-long when making UNIQUE(source_id + identifier) constraint under utf8mb4.
ALTER TABLE CHANGE COLUMN identifier identifier VARCHAR(190);
