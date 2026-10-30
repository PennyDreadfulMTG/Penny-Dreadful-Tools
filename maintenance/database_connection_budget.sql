-- Run as a database administrator after deploying the connection lifecycle fixes.
-- This account is shared by decksite, logsite, bots, and maintenance jobs.
-- The production main site can use 32 connections (16 workers x 2 databases),
-- and logsite can use 8 (4 workers x a bounded pool of 2).
-- An account limit of 40 leaves no headroom for background jobs or worker startup.
-- Raise only this account's limit; do not change the server-wide connection limits.
ALTER USER 'pennydreadful'@'localhost' WITH MAX_USER_CONNECTIONS 80;

-- Verify the persisted account-specific setting. Existing sessions report their
-- original session limit, so also verify @@session.max_user_connections through
-- a NEW connection as pennydreadful. No database restart is needed.
SELECT User, Host, max_user_connections
FROM mysql.user WHERE User = 'pennydreadful' AND Host = 'localhost';

-- Rollback to the previous effective limit:
-- ALTER USER 'pennydreadful'@'localhost' WITH MAX_USER_CONNECTIONS 40;
