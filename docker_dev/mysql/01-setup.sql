-- CREATE USER 'pennydreadful'@'%' IDENTIFIED BY '';

GRANT ALL PRIVILEGES ON cards.* TO 'pennydreadful'@'%';
GRANT ALL PRIVILEGES ON decksite.* TO 'pennydreadful'@'%';
GRANT ALL PRIVILEGES ON pdlogs.* TO 'pennydreadful'@'%';
GRANT ALL PRIVILEGES ON prices.* TO 'pennydreadful'@'%';
GRANT CREATE ON *.* TO 'pennydreadful'@'%';

CREATE DATABASE decksite;
CREATE DATABASE cards;
CREATE DATABASE pdlogs;
CREATE DATABASE prices;
