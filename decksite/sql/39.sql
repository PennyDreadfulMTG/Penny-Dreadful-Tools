-- We're going to store omw in cache now for decks that are done playing all the games they are ever going to play.
ALTER TABLE deck_cache ADD COLUMN omw DECIMAL;
