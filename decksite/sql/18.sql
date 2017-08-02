-- Prevent key-too-long under utf8mb4.
ALTER TABLE competition_type CHANGE COLUMN name name VARCHAR(190);
