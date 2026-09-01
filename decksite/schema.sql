
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;
DROP TABLE IF EXISTS `archetype`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `archetype` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` text DEFAULT NULL,
  `description` text DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `archetype` WRITE;
/*!40000 ALTER TABLE `archetype` DISABLE KEYS */;
INSERT INTO `archetype` VALUES
(1,'Aggro','Kill the opponent quickly by attacking with creatures.'),
(2,'Combo','Execute a specific interaction which immediately wins the game or generates insurmountable advantage.'),
(3,'Control','Answer threats while generating card advantage.'),
(4,'Aggro-Combo',''),
(5,'Aggro-Control',''),
(6,'Combo-Control',''),
(7,'Midrange',''),
(8,'Ramp','Accelerate mana to play big threats before they can be answered.'),
(9,'Unclassified','Do not add decks to this archetype');
/*!40000 ALTER TABLE `archetype` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `archetype_closure`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `archetype_closure` (
  `ancestor` int(11) NOT NULL,
  `descendant` int(11) NOT NULL,
  `depth` int(11) DEFAULT NULL,
  PRIMARY KEY (`ancestor`,`descendant`),
  KEY `descendant` (`descendant`),
  CONSTRAINT `archetype_closure_ibfk_1` FOREIGN KEY (`ancestor`) REFERENCES `archetype` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `archetype_closure_ibfk_2` FOREIGN KEY (`descendant`) REFERENCES `archetype` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `archetype_closure` WRITE;
/*!40000 ALTER TABLE `archetype_closure` DISABLE KEYS */;
/*!40000 ALTER TABLE `archetype_closure` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `competition`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `start_date` int(11) NOT NULL,
  `end_date` int(11) NOT NULL,
  `name` text DEFAULT NULL,
  `url` text DEFAULT NULL,
  `competition_series_id` int(11) NOT NULL,
  `top_n` int(11) NOT NULL,
  `is_locked` tinyint(1) NOT NULL DEFAULT 0,
  `competition_flag_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_u_name` (`name`(142)),
  KEY `competition_series_id` (`competition_series_id`),
  KEY `competition_flag_id` (`competition_flag_id`),
  CONSTRAINT `competition_ibfk_1` FOREIGN KEY (`competition_series_id`) REFERENCES `competition_series` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `competition_ibfk_2` FOREIGN KEY (`competition_flag_id`) REFERENCES `competition_flag` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition` WRITE;
/*!40000 ALTER TABLE `competition` DISABLE KEYS */;
INSERT INTO `competition` VALUES
(1,1470034800,1475305200,'League September 2016','http://pennydreadfulmagic.com/league/',1,8,0,NULL),
(2,1475305200,1477983600,'League October 2016','http://pennydreadfulmagic.com/league/',1,8,0,NULL),
(3,1477983600,1480579200,'League November 2016','http://pennydreadfulmagic.com/league/',1,8,0,NULL);
/*!40000 ALTER TABLE `competition` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `competition_flag`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_flag` (
  `id` int(11) NOT NULL,
  `name` varchar(190) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_flag` WRITE;
/*!40000 ALTER TABLE `competition_flag` DISABLE KEYS */;
INSERT INTO `competition_flag` VALUES
(1,'Season Championship'),
(2,'Season Kick Off'),
(3,'The Penny Dreadful 500'),
(4,'Super Saturday');
/*!40000 ALTER TABLE `competition_flag` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `competition_series`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_series` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(190) NOT NULL,
  `competition_type_id` int(11) NOT NULL,
  `sponsor_id` int(11) DEFAULT NULL,
  `day_of_week` smallint(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `competition_type_id` (`competition_type_id`),
  KEY `sponsor_id` (`sponsor_id`),
  CONSTRAINT `competition_series_ibfk_1` FOREIGN KEY (`competition_type_id`) REFERENCES `competition_type` (`id`),
  CONSTRAINT `competition_series_ibfk_2` FOREIGN KEY (`sponsor_id`) REFERENCES `sponsor` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_series` WRITE;
/*!40000 ALTER TABLE `competition_series` DISABLE KEYS */;
INSERT INTO `competition_series` VALUES
(1,'League',1,3,NULL),
(2,'Penny Dreadful Thursdays',2,1,7),
(3,'Penny Paradise',2,2,NULL),
(4,'Penny Dreadful Sundays',2,1,3),
(5,'Penny Dreadful Mondays',2,1,4),
(6,'Penny Dreadful Saturdays',2,1,2),
(7,'APAC Penny Dreadful Sundays',2,NULL,3),
(8,'Penny Dreadful FNM',2,NULL,1),
(9,'Penny Dreadful Tuesdays',2,NULL,5),
(10,'Penny Dreadful EU Wednesdays',2,NULL,6);
/*!40000 ALTER TABLE `competition_series` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `competition_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `competition_type` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(190) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `competition_type` WRITE;
/*!40000 ALTER TABLE `competition_type` DISABLE KEYS */;
INSERT INTO `competition_type` VALUES
(2,'Gatherling'),
(1,'League');
/*!40000 ALTER TABLE `competition_type` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `db_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `db_version` (
  `version` int(11) NOT NULL,
  UNIQUE KEY `version` (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `db_version` WRITE;
/*!40000 ALTER TABLE `db_version` DISABLE KEYS */;
INSERT INTO `db_version` VALUES
(1),
(2),
(3),
(4),
(5),
(6),
(7),
(8),
(9),
(10),
(11),
(12),
(13),
(14),
(15),
(16),
(17),
(18),
(19),
(20),
(22),
(23),
(24),
(25),
(26),
(27),
(28),
(29),
(30),
(31),
(32),
(33),
(34),
(35),
(36),
(37),
(38),
(39),
(40),
(41),
(42),
(43),
(44),
(45),
(46),
(47),
(48),
(49),
(50),
(51),
(52),
(53),
(54),
(55),
(56),
(57),
(58),
(59),
(60),
(61),
(62),
(63),
(64),
(65),
(66),
(67),
(68),
(69),
(70),
(71),
(72),
(73),
(74),
(75),
(76);
/*!40000 ALTER TABLE `db_version` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `deck`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `deck` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `person_id` int(11) NOT NULL,
  `source_id` int(11) NOT NULL,
  `identifier` varchar(190) DEFAULT NULL,
  `name` text DEFAULT NULL,
  `created_date` int(11) NOT NULL,
  `updated_date` int(11) NOT NULL,
  `competition_id` int(11) DEFAULT NULL,
  `url` text DEFAULT NULL,
  `archetype_id` int(11) DEFAULT NULL,
  `resource_uri` text DEFAULT NULL,
  `featured_card` text DEFAULT NULL,
  `score` int(11) DEFAULT NULL,
  `thumbnail_url` text DEFAULT NULL,
  `small_thumbnail_url` text DEFAULT NULL,
  `finish` int(11) DEFAULT NULL,
  `decklist_hash` char(40) DEFAULT NULL,
  `retired` tinyint(1) DEFAULT 0,
  `reviewed` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `deck_source_id_identifier` (`source_id`,`identifier`),
  KEY `person_id` (`person_id`),
  KEY `competition_id` (`competition_id`),
  KEY `archetype_id` (`archetype_id`),
  KEY `deck_hash` (`decklist_hash`),
  CONSTRAINT `deck_ibfk_1` FOREIGN KEY (`person_id`) REFERENCES `person` (`id`),
  CONSTRAINT `deck_ibfk_2` FOREIGN KEY (`source_id`) REFERENCES `source` (`id`),
  CONSTRAINT `deck_ibfk_3` FOREIGN KEY (`competition_id`) REFERENCES `competition` (`id`),
  CONSTRAINT `deck_ibfk_4` FOREIGN KEY (`archetype_id`) REFERENCES `archetype` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `deck` WRITE;
/*!40000 ALTER TABLE `deck` DISABLE KEYS */;
/*!40000 ALTER TABLE `deck` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `deck_archetype_change`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `deck_archetype_change` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `changed_date` int(11) NOT NULL,
  `deck_id` int(11) NOT NULL,
  `archetype_id` int(11) NOT NULL,
  `person_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `deck_id` (`deck_id`),
  KEY `archetype_id` (`archetype_id`),
  KEY `person_id` (`person_id`),
  CONSTRAINT `deck_archetype_change_ibfk_1` FOREIGN KEY (`deck_id`) REFERENCES `deck` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `deck_archetype_change_ibfk_2` FOREIGN KEY (`archetype_id`) REFERENCES `archetype` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `deck_archetype_change_ibfk_3` FOREIGN KEY (`person_id`) REFERENCES `person` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `deck_archetype_change` WRITE;
/*!40000 ALTER TABLE `deck_archetype_change` DISABLE KEYS */;
/*!40000 ALTER TABLE `deck_archetype_change` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `deck_cache`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `deck_cache` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `deck_id` int(11) NOT NULL,
  `colors` text DEFAULT NULL,
  `colored_symbols` text DEFAULT NULL,
  `legal_formats` text DEFAULT NULL,
  `normalized_name` text DEFAULT NULL,
  `omw` decimal(3,2) DEFAULT NULL,
  `wins` int(11) NOT NULL DEFAULT 0,
  `losses` int(11) NOT NULL DEFAULT 0,
  `draws` int(11) NOT NULL DEFAULT 0,
  `active_date` int(11) NOT NULL,
  `similarity` int(11) DEFAULT NULL,
  `color_sort` int(11) DEFAULT NULL,
  `season_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `deck_id` (`deck_id`),
  KEY `season_id` (`season_id`),
  CONSTRAINT `deck_cache_ibfk_1` FOREIGN KEY (`deck_id`) REFERENCES `deck` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `deck_cache_ibfk_2` FOREIGN KEY (`season_id`) REFERENCES `season` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `deck_cache` WRITE;
/*!40000 ALTER TABLE `deck_cache` DISABLE KEYS */;
/*!40000 ALTER TABLE `deck_cache` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `deck_card`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `deck_card` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `deck_id` int(11) NOT NULL,
  `card` varchar(190) CHARACTER SET utf8mb3 COLLATE utf8mb3_uca1400_ai_ci DEFAULT NULL,
  `n` int(11) NOT NULL,
  `sideboard` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `deck_card_deck_id_card_sideboard` (`deck_id`,`card`,`sideboard`),
  KEY `idx_card` (`card`),
  KEY `idx_card_deck_id_sideboard_n` (`card`,`deck_id`,`sideboard`,`n`),
  KEY `idx_deck_id_card_n_sideboard` (`deck_id`,`card`,`n`,`sideboard`),
  CONSTRAINT `deck_card_ibfk_1` FOREIGN KEY (`deck_id`) REFERENCES `deck` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `deck_card` WRITE;
/*!40000 ALTER TABLE `deck_card` DISABLE KEYS */;
/*!40000 ALTER TABLE `deck_card` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `deck_match`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `deck_match` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `match_id` int(11) NOT NULL,
  `deck_id` int(11) NOT NULL,
  `games` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `deck_id` (`deck_id`),
  KEY `match_id` (`match_id`),
  CONSTRAINT `deck_match_ibfk_2` FOREIGN KEY (`deck_id`) REFERENCES `deck` (`id`),
  CONSTRAINT `deck_match_ibfk_3` FOREIGN KEY (`match_id`) REFERENCES `match` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `deck_match` WRITE;
/*!40000 ALTER TABLE `deck_match` DISABLE KEYS */;
/*!40000 ALTER TABLE `deck_match` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `doorprize`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `doorprize` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `competition_name` text NOT NULL,
  `winner_name` text NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `competition_name` (`competition_name`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `doorprize` WRITE;
/*!40000 ALTER TABLE `doorprize` DISABLE KEYS */;
/*!40000 ALTER TABLE `doorprize` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `match`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `match` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `date` int(11) NOT NULL,
  `round` int(11) DEFAULT NULL,
  `elimination` int(11) DEFAULT NULL,
  `mtgo_id` int(13) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_mtgo_id` (`mtgo_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `match` WRITE;
/*!40000 ALTER TABLE `match` DISABLE KEYS */;
/*!40000 ALTER TABLE `match` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `permission_changes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `permission_changes` (
  `discord_id` bigint(20) DEFAULT NULL,
  `permission` varchar(255) CHARACTER SET utf8mb3 COLLATE utf8mb3_uca1400_ai_ci DEFAULT NULL,
  UNIQUE KEY `unique_discord_id` (`discord_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `permission_changes` WRITE;
/*!40000 ALTER TABLE `permission_changes` DISABLE KEYS */;
/*!40000 ALTER TABLE `permission_changes` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `person`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `person` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` text DEFAULT NULL,
  `tappedout_username` varchar(50) DEFAULT NULL,
  `mtgo_username` varchar(50) DEFAULT NULL,
  `mtggoldfish_username` varchar(50) DEFAULT NULL,
  `discord_id` bigint(20) DEFAULT NULL,
  `banned` tinyint(1) NOT NULL DEFAULT 0,
  `elo` int(11) NOT NULL DEFAULT 1500,
  `locale` varchar(8) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tappedout_username` (`tappedout_username`),
  UNIQUE KEY `mtgo_username` (`mtgo_username`),
  UNIQUE KEY `mtggoldfish_username` (`mtggoldfish_username`),
  UNIQUE KEY `discord_id` (`discord_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `person` WRITE;
/*!40000 ALTER TABLE `person` DISABLE KEYS */;
/*!40000 ALTER TABLE `person` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `person_alias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `person_alias` (
  `person_id` int(11) NOT NULL,
  `alias` varchar(190) CHARACTER SET utf8mb3 COLLATE utf8mb3_uca1400_ai_ci NOT NULL,
  PRIMARY KEY (`person_id`,`alias`),
  CONSTRAINT `person_alias_ibfk_1` FOREIGN KEY (`person_id`) REFERENCES `person` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `person_alias` WRITE;
/*!40000 ALTER TABLE `person_alias` DISABLE KEYS */;
/*!40000 ALTER TABLE `person_alias` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `person_note`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `person_note` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_date` int(11) NOT NULL,
  `creator_id` int(11) NOT NULL,
  `subject_id` int(11) NOT NULL,
  `note` text NOT NULL,
  PRIMARY KEY (`id`),
  KEY `creator_id` (`creator_id`),
  KEY `subject_id` (`subject_id`),
  CONSTRAINT `person_note_ibfk_1` FOREIGN KEY (`creator_id`) REFERENCES `person` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `person_note_ibfk_2` FOREIGN KEY (`subject_id`) REFERENCES `person` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `person_note` WRITE;
/*!40000 ALTER TABLE `person_note` DISABLE KEYS */;
/*!40000 ALTER TABLE `person_note` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `rotation_runs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `rotation_runs` (
  `number` tinyint(3) unsigned NOT NULL,
  `name` varchar(190) NOT NULL,
  `season_id` int(11) NOT NULL,
  PRIMARY KEY (`number`,`name`,`season_id`),
  KEY `idx_name` (`name`),
  KEY `idx_season_id` (`season_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `rotation_runs` WRITE;
/*!40000 ALTER TABLE `rotation_runs` DISABLE KEYS */;
/*!40000 ALTER TABLE `rotation_runs` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `rule`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `rule` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `archetype_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `archetype_id` (`archetype_id`),
  CONSTRAINT `rule_ibfk_1` FOREIGN KEY (`archetype_id`) REFERENCES `archetype` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `rule` WRITE;
/*!40000 ALTER TABLE `rule` DISABLE KEYS */;
/*!40000 ALTER TABLE `rule` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `rule_card`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `rule_card` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `rule_id` int(11) NOT NULL,
  `card` varchar(190) NOT NULL,
  `include` int(11) NOT NULL,
  `n` int(11) NOT NULL,
  `sideboard` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_rule_id_card_include_n` (`rule_id`,`card`,`include`,`n`),
  CONSTRAINT `rule_card_ibfk_1` FOREIGN KEY (`rule_id`) REFERENCES `rule` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `rule_card` WRITE;
/*!40000 ALTER TABLE `rule_card` DISABLE KEYS */;
/*!40000 ALTER TABLE `rule_card` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `season`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `season` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `number` tinyint(4) NOT NULL,
  `code` varchar(3) NOT NULL,
  `start_date` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `number` (`number`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `season` WRITE;
/*!40000 ALTER TABLE `season` DISABLE KEYS */;
INSERT INTO `season` VALUES
(1,1,'EMN',1469174400),
(2,2,'KLD',1475308800),
(3,3,'AER',1484985600),
(4,4,'AKH',1493452800),
(5,5,'HOU',1500105600),
(6,6,'XLN',1506758400),
(7,7,'RIX',1516435200),
(8,8,'DOM',1524812400),
(9,9,'M19',1531465200),
(10,10,'GRN',1538722800),
(11,11,'RNA',1548403200),
(12,12,'WAR',1556866800),
(13,13,'M20',1562914800),
(14,14,'ELD',1570172400),
(15,15,'THB',1579852800),
(16,16,'IKO',1587711600),
(17,17,'M21',1594364400),
(18,18,'ZNR',1601622000),
(19,19,'KHM',1613116800),
(20,20,'STX',1619766000),
(21,21,'AFR',1627628400);
/*!40000 ALTER TABLE `season` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `source`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `source` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `source` WRITE;
/*!40000 ALTER TABLE `source` DISABLE KEYS */;
INSERT INTO `source` VALUES
(2,'Gatherling'),
(3,'League'),
(4,'MTG Goldfish'),
(1,'Tapped Out');
/*!40000 ALTER TABLE `source` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
DROP TABLE IF EXISTS `sponsor`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sponsor` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(190) NOT NULL,
  `url` varchar(190) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `url` (`url`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `sponsor` WRITE;
/*!40000 ALTER TABLE `sponsor` DISABLE KEYS */;
INSERT INTO `sponsor` VALUES
(1,'Cardhoarder','https://cardhoarder.com/'),
(2,'Manatraders','https://www.manatraders.com/'),
(3,'MTGO Traders','https://www.mtgotraders.com/'),
(4,'MTGO','https://mtgo.com');
/*!40000 ALTER TABLE `sponsor` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

