import os
import bot

# Check that we can fetch card images.
def test_imagedownload():
  filepath = bot.config.get("image_dir") + "/" + "island.jpg" 
  if (bot.acceptable_file(filepath)):
    os.remove(filepath)
  assert bot.download_image("Island", 0) != None

# Check that we can fall back to the Gatherer images if all else fails.
def test_fallbackimagedownload():
  filepath = bot.config.get("image_dir") + "/" + "avon_island.jpg" 
  if (bot.acceptable_file(filepath)):
    os.remove(filepath)
  assert bot.download_image("Avon_Island", 26301) != None    

# Search for a single card via full name
def test_solo_query():
  names = bot.parse_queries("[Gilder Bairn]")
  assert len(names) == 1
  assert names[0] == "gilder bairn"
  cards = bot.cards_from_queries(names)
  assert len(cards) == 1

# Two cards, via full name
def test_double_query():
  names = bot.parse_queries("[Mother of Runes] [Ghostfire]")
  assert len(names) == 2
  cards = bot.cards_from_queries(names)
  assert len(cards) == 2

# The following two sets assume that Kamahl is a long dead character, and is getting no new cards.
# If wizards does an Onslaught/Odyssey throwback in some supplimental product, they may start failing. 
def test_legend_query():
  names = bot.parse_queries("[Kamahl]")
  assert len(names) == 1
  cards = bot.cards_from_queries(names)
  assert len(cards) == 2

def test_partial_query():
  names = bot.parse_queries("[Kamahl's]")
  assert len(names) == 1
  cards = bot.cards_from_queries(names)
  assert len(cards) == 3

# Check that the list of legal cards is being fetched correctly.
def test_legality_list():
  bot.update_legality()
  assert len(bot.legal_cards) > 0