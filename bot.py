import hashlib, json, os, re, random, string, unicodedata, urllib.request
import discord
import config, fetcher, oracle, search

# Globals
legal_cards = []
client = discord.Client()
config = config.Config()
oracle = oracle.Oracle()

def init():
  update_legality()
  client.run(config.get("token"))

def update_legality():
  global legal_cards
  legal_cards = fetcher.Fetcher().legal_cards()
  print("Legal cards: {0}".format(str(len(legal_cards))))

def escape(str_input):
  return '+'.join(str_input.split(' ')).lower()

def better_image(cards):
  c = '|'.join(card.name for card in cards)
  return "http://magic.bluebones.net/proxies/?c=" + escape(c)

def http_image(multiverse_id):
  return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(multiverse_id)  +'.jpg'

# Given a list of cards return one (aribtrarily) for each unique name in the list.
def uniqify_cards(cards):
  # Remove multiple printings of the same card from the result set.
  results = {}
  for card in cards:
    results[card.name.lower()] = card
  return results.values()

def acceptable_file(filepath):
  return os.path.isfile(filepath) and os.path.getsize(filepath) > 0

def basename(cards):
  return '_'.join(re.sub('[^a-z-]', '-', unaccent(card.name).lower()) for card in cards)

def unaccent(s):
  return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

def download_image(cards):
  image_dir = config.get("image_dir")
  imagename = basename(cards)
  # Hash the filename if it's otherwise going to be too large to use.
  if len(imagename) > 240:
    imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
  filename = imagename + '.jpg'
  filepath = config.get("image_dir") + "/" + filename
  if acceptable_file(filepath):
    return filepath
  print("Trying to get first choice image for " + ', '.join(card.name for card in cards))
  try:
    urllib.request.urlretrieve(better_image(cards), filepath)
  except urllib.error.HTTPError as error:
    print("HTTP Error: {0}".format(error))
  if acceptable_file(filepath):
    return filepath
  multiverse_id = cards[0].multiverse_id
  if multiverse_id > 0:
    print("Trying to get fallback image for " + imagename)
    try:
      urllib.request.urlretrieve(http_image(multiverse_id), filepath)
    except urllib.error.HTTPError as error:
      print("HTTP Error: {0}".format(error))
    if acceptable_file(filepath):
      return filepath
  return None

def parse_queries(content):
  queries = re.findall('\[([^\]]*)\]', content)
  return [query.lower() for query in queries]

def cards_from_queries(queries):
  all_cards = []
  for query in queries:
    cards = cards_from_query(query)
    if len(cards) > 0:
      all_cards.extend(cards)
  return all_cards

def cards_from_query(query):
  # Skip searching if the request is too short.
  if len(query) <= 2:
      return []
  cards = oracle.search(query)
  cards = [card for card in cards if card.type != "Vanguard" and card.layout != 'token']
  # First look for an exact match.
  for card in cards:
    if card.name.lower() == query:
      return [card]
  # If not found, use cards that start with the query and a punctuation char.
  results = [card for card in cards if card.name.lower().startswith(query + " ") or card.name.lower().startswith(query + ",") ]
  if len(results) > 0:
    return uniqify_cards(results)
  # If not found, use cards that start with the query.
  results = [card for card in cards if card.name.lower().startswith(query)]
  if len(results) > 0:
    return uniqify_cards(results)
  # If we didn't find any of those then use all search results.
  return uniqify_cards(cards)

def legal_emoji(card, verbose = False):
  if card.name.lower().strip() in legal_cards:
    return ':white_check_mark:'
  s = ':no_entry_sign:'
  if verbose:
    s += ' (not legal in PD)'
  return s

def complex_search(query):
  print("Searching for %s" % query)
  return search.Search(query).fetchall()

async def post_cards(cards, channel):
  if len(cards) == 0:
    await client.send_message(channel, 'No matches.')
    return
  more_text = ''
  if len(cards) > 10:
    more_text = ' and ' + str(len(cards) - 4) + ' more.'
    cards = cards[:4]
  if len(cards) == 1:
    card = cards[0]
    mana_cost = card.mana_cost or ''
    legal = legal_emoji(card, True)
    pt = str(card.power) + '/' + str(card.toughness) if 'Creature' in card.type else ''
    text = string.Template("$name $mana_cost — $type — $legal").substitute(name=card.name, mana_cost=mana_cost, type=card.type, text=card.text, legal=legal, pt=pt)
  else:
    text = ', '.join(string.Template("$name $legal").substitute(name = card.name, legal = legal_emoji(card)) for card in cards)
    text += more_text
  image_file = download_image(cards)
  await client.send_message(channel, text)
  if image_file is None:
    await client.send_message(channel, 'No image available.')
  else:
    await client.send_file(channel, image_file)

async def respond_to_card_names(message):
  # Don't parse messages with Gatherer URLs because they use square brackets in the querystring.
  if "gatherer.wizards.com" in message.content.lower():
    return
  queries = parse_queries(message.content)
  if len(queries) == 0:
    return
  cards = cards_from_queries(queries)
  await post_cards(cards, message.channel)

async def respond_to_command(message):
  if message.content.startswith("!random"):
    name = random.choice(legal_cards)
    cards = cards_from_query(name)
    await post_cards(cards, message.channel)
  elif message.content.startswith("!reload"):
    update_legality()
    await client.send_message(message.channel, "Reloaded list of legal cards.")
  elif message.content.startswith('!search '):
    cards = complex_search(message.content[len('!search '):])
    await post_cards(cards, message.channel)

@client.event
async def on_message(message):
  # We do not want the bot to reply to itself.
  if message.author == client.user:
    return
  if message.content.startswith("!"):
    await respond_to_command(message)
  else:
    await respond_to_card_names(message)

@client.event
async def on_ready():
  print('Logged in as')
  print(client.user.name)
  print(client.user.id)
  print('------')
