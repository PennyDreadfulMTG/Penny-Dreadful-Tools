import json, discord, os, string, re, random, hashlib, unicodedata, urllib.request
import fetcher, oracle, config

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

def normalize_filename(str_input):
  # Remove spaces
  str_input = '-'.join(str_input.split(' ')).lower()
  # Remove Pipes
  str_input = '-'.join(str_input.split('|')).lower()
  # Remove nasty accented characters.
  return ''.join((c for c in unicodedata.normalize('NFD', str_input) if unicodedata.category(c) != 'Mn'))

def escape(str_input):
  return '+'.join(str_input.split(' ')).lower()

def better_image(cardname):
  return "http://magic.bluebones.net/proxies/?c=" + escape(cardname)

def http_image(uid):
  return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(uid)  +'.jpg'

# Given a list of cards return one (aribtrarily) for each unique name in the list.
def uniqify_cards(cards):
  # Remove multiple printings of the same card from the result set.
  results = {}
  for card in cards:
    results[card.name.lower()] = card
  return results.values()

def acceptable_file(filepath):
  return os.path.isfile(filepath) and os.path.getsize(filepath) > 0

def download_image(cardname, uid):
  image_dir = config.get("image_dir")
  basename = normalize_filename(cardname)
  # Hash the filename if it's otherwise going to be too large to use.
  if len(basename) > 255:
    basename = hashlib.md5(basename.encode('utf-8')).hexdigest()
  filename = basename + '.jpg'
  filepath = config.get("image_dir") + "/" + filename
  if acceptable_file(filepath):
    return filepath
  print("Trying to get first choice image for " + cardname)
  try:
    urllib.request.urlretrieve(better_image(cardname), filepath)
  except urllib.error.HTTPError as error:
    print("HTTP Error: {0}".format(error))
  if acceptable_file(filepath):
    return filepath
  if uid > 0:
    print("Trying to get fallback image for " + cardname)
    try:
      urllib.request.urlretrieve(http_image(uid), filepath)
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

async def post_card(card, channel):
  resp = string.Template("$name $mana_cost — $type — $legal").substitute(name=card.name, mana_cost=card.mana_cost if card.mana_cost else '', type=card.type, text=card.text, legal=":white_check_mark:" if card.name.lower().strip() in legal_cards else ":no_entry_sign: (not legal in PD)", pt=str(card.power)+ "/" + str(card.toughness) if "Creature" in card.type else '')
  filename = download_image(card.name, card.multiverse_id)
  await client.send_message(channel, resp)
  if filename is None:
    await client.send_message(channel, card.text)
  else:
    await client.send_file(channel, filename)

async def post_cards(cards, channel):
  tmp = string.Template("$name $legal, ")
  text = ""
  images = ""
  more_text = ""
  if (len(cards) > 10):
    more_text = " and " + str(len(cards) - 4) + " more."
    cards = cards[:4]
  for card in cards:
    text = text + tmp.substitute(name=card.name, legal=":white_check_mark:" if card.name.lower().strip() in legal_cards else ":no_entry_sign:")
    images = images + "|" + escape(card.name)
  await client.send_message(channel, text.strip(", ") + more_text)
  filename = download_image(images, 0)
  if filename is None:
    await client.send_message(channel, "No image available")
  else:
    await client.send_file(channel, filename)

async def respond_to_card_names(message):
  # Don't parse messages with Gatherer URLs because they use square brackets in the querystring.
  if "gatherer.wizards.com" in message.content.lower():
    return
  queries = parse_queries(message.content)
  if len(queries) == 0:
    return
  cards = cards_from_queries(queries)
  if len(cards) > 1:
    await post_cards(cards, message.channel)
  elif len(cards) == 1:
    await post_card(cards[0], message.channel)

async def respond_to_command(message):
  if message.content.startswith("!random"):
    name = random.choice(legal_cards)
    cards = cards_from_query(name)
    await post_card(cards[0], message.channel)
  elif message.content.startswith("!reload"):
    update_legality()
    await client.send_message(message.channel, "Reloaded list of legal cards.")

@client.event
async def on_message(message):
  # We do not want the bot to reply to itself.
  if message.author == client.user:
    return
  if message.content.startswith("!"):
    await respond_to_command(message)
  await respond_to_card_names(message)

@client.event
async def on_ready():
  print('Logged in as')
  print(client.user.name)
  print(client.user.id)
  print('------')
