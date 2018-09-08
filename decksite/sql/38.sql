-- Add a unique index to competition.name so that we can use INSERT IGNORE INTO to create new leagues without fear of creating two or more. See #4806.
CREATE UNIQUE INDEX idx_u_name ON competition (name(142));
