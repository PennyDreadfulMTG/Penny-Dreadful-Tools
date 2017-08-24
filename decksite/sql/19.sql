-- Occassionally we have to manually delete league matches. Make it a little easier.
ALTER TABLE deck_match DROP FOREIGN KEY deck_match_ibfk_1;
ALTER TABLE deck_match ADD FOREIGN KEY(match_id) REFERENCES `match`(id) ON UPDATE CASCADE ON DELETE CASCADE;
