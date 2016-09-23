from mtgsdk import Card
import json, discord, os, string, re, random
import urllib.request

# Globals
cache = {}
legal_cards = []
client = discord.Client()

def init():
  for line in urllib.request.urlopen('http://pdmtgo.com/legal_cards.txt').readlines():
    legal_cards.append(line.decode('latin-1').lower().strip())
  print("Legal cards: " + str(len(legal_cards)))
  client.run(os.environ['TOKEN'])

def reduce(str_input):
  str_input = '-'.join(str_input.split(' ')).lower()
  return '-'.join(str_input.split('|')).lower()

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

def acceptable_file(filename):
  return os.path.isfile(filename) and os.path.getsize(filename) > 0

def download_image(cardname, uid):
  filename = reduce(cardname) + '.jpg'
  if acceptable_file(filename):
    return filename
  urllib.request.urlretrieve(better_image(cardname), filename)
  if acceptable_file(filename):
    return filename
  if uid > 0:
    urllib.request.urlretrieve(http_image(uid), filename)
    if acceptable_file(filename):
      return filename
  return None

def card_search(query):
  if query not in cache:
    print("Requesting API for " + query)
    cache[query] = Card.where(name = query).all()
  return cache[query]

def parse_queries(content):
  queries = re.findall('\[([^\]]*)\]', content)
  return [query.lower() for query in queries]

def cards_from_queries(queries, message):
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
  cards = card_search(query)
  cards = [card for card in cards if card.type != "Vanguard"]
  # First look for an exact match.
  for card in cards:
    if card.name.lower() == query:
      return [card]
  # If not found, use cards that start with the query.
  results = [card for card in cards if card.name.lower().startswith(query)]
  if len(results) > 0:
    return uniqify_cards(results)
  # If we didn't find any of those then use all search results.
  return uniqify_cards(cards)

async def post_card(card, channel):
  resp = string.Template("$name $mana_cost — $type — $legal").substitute(name=card.name, mana_cost=card.mana_cost if card.mana_cost else '', type=card.type, text=card.text, legal=":white_check_mark:" if card.name.lower().strip() in legal_cards else ":no_entry_sign: (not legal in PD)", pt=str(card.power)+ "/" + str(card.toughness) if "Creature" in card.type else '')
  await client.send_message(channel, resp)
  filename = download_image(card.name, card.multiverse_id)
  if filename is None:
    await client.send_message(channel, card.text)
  else:
    await client.send_file(channel, filename)

async def post_cards(cards, channel):
  tmp = string.Template("$name $legal, ")
  text = ""
  images = ""
  for card in cards:
    text = text + tmp.substitute(name=card.name, legal=":white_check_mark:" if card.name.lower().strip() in legal_cards else ":no_entry_sign:")
    images = images + "|" + escape(card.name)
  await client.send_message(channel, text.strip(", "))
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
  cards = cards_from_queries(queries, message)
  if len(cards) > 1:
    await post_cards(cards, message.channel)
  elif len(cards) == 1:
    await post_card(cards[0], message.channel)

async def respond_to_command(message):
  if message.content.startswith("!random"):
    name = random.choice(legal_cards)
    cards = cards_from_query(name)
    await post_card(cards[0], message.channel)

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

init()
