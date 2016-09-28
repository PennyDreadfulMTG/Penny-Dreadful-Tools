import os

import bot
import oracle


# Check that we can fetch card images.
def test_imagedownload():
  filepath = bot.config.get("image_dir") + "/" + "island.jpg"
  if (bot.acceptable_file(filepath)):
    os.remove(filepath)
  card = oracle.Card({'name': 'Island'})
  assert bot.download_image([card]) != None

# Check that we can fall back to the Gatherer images if all else fails.
def test_fallbackimagedownload():
  filepath = bot.config.get("image_dir") + "/" + "avon_island.jpg"
  if (bot.acceptable_file(filepath)):
    os.remove(filepath)
  card = oracle.Card({'name': 'Avon Island', 'multiverse_id': 26301})
  assert bot.download_image([card]) != None

# Check that we can succesfully fail at getting an image
def test_noimageavailable():
  card = oracle.Card({'name': "Barry's Land", 'multiverse_id': 0})
  assert bot.download_image([card]) == None

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

def test_legality_emoji():
  legal_card = bot.cards_from_query(bot.legal_cards[0])[0]
  assert bot.legal_emoji(legal_card) == ':white_check_mark:'
  illegal_card = bot.cards_from_query("black lotus")[0]
  assert bot.legal_emoji(illegal_card) == ':no_entry_sign:'
  assert bot.legal_emoji(illegal_card, True) == ':no_entry_sign: (not legal in PD)'

def test_accents():
  cards = bot.cards_from_query("Lim-Dûl the Necromancer")
  assert len(cards) == 1
  cards = bot.cards_from_query("Séance")
  assert len(cards) == 1

  # The following two don't currently work.  But should be turned on once they do.

  #cards = bot.cards_from_query("Lim-Dul the Necromancer")
  #assert len(cards) == 1
  #cards = bot.cards_from_query("Seance")
  #assert len(cards) == 1

def test_aether():
  cards = bot.cards_from_query("Æther Spellbomb")
  assert len(cards) == 1
  #cards = bot.cards_from_query("aether Spellbomb")
  #assert len(cards) == 1

def test_mana_emoji():
  assert bot.prettify_mana_cost("{2}{U}{B}") == ':02::UU::BB:'
  assert bot.prettify_mana_cost("{2/W}{2/U}, {T}") == ':2W::2U:, :TT:'
  assert bot.prettify_mana_cost("{U/P}") == ':UP:'
  assert bot.prettify_mana_cost("{15}") == ':15:'
  assert bot.prettify_mana_cost("{20}") == ':20:'
  assert bot.prettify_mana_cost("{T}, {Q}, {T}, {Q}, {T}: Tap all creatures with globe counters on them.") == ':TT:, :QQ:, :TT:, :QQ:, :TT:: Tap all creatures with globe counters on them.'
  