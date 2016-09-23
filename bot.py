from mtgsdk import Card
import json, discord, os, string
import urllib.request

prop = {'name','multiverse_id','layout','names','mana_cost','cmc','colors','type','supertypes','subtypes','rarity','text','flavor','artist','number','power','toughness','loyalty','variations','watermark','border','timeshifted','hand','life','reserved','release_date','starter','rulings','foreign_names','printings','original_text','original_type','legalities','source','image_url','set','set_name','id'}
run = 'card_adv = Card'
def adv(str_input):
  return '='.join(str_input.split(' ')).lower()
def reduce(str_input):
  str_input = '-'.join(str_input.split(' ')).lower()
  return '-'.join(str_input.split('|')).lower()
def escape(str_input):
  return '+'.join(str_input.split(' ')).lower()
def better_image(cardname):
  return "http://magic.bluebones.net/proxies/?c=" + escape(cardname)
def http_image(uid):
  return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(uid)  +'.jpg'
def http_address(set,name):
  return 'http://store.tcgplayer.com/magic/'+reduce(set)+'/'+reduce(name)
def http_parse(str_input):
  return '%20'.join(str_input.split(' '))

def downloadimage(cardname, uid):
  filename = reduce(cardname) + '.jpg'
  if os.path.isfile(filename):
    if os.path.getsize(filename) > 0:
      return filename
  urllib.request.urlretrieve(better_image(cardname), filename)
  if os.path.getsize(filename) > 0:
    return filename
  if uid > 0:
    urllib.request.urlretrieve(http_image(uid), filename)
    return filename
  return None

cache = {}
def cardsearch(name):
  if name not in cache:
    print("Requesting API for " + name)
    cache[name] = Card.where(name=name).all()
  return cache[name]


legalcards = []
for line in urllib.request.urlopen('http://pdmtgo.com/legal_cards.txt').readlines():
  legalcards.append(line.decode('latin-1').lower().strip())

print("Legal cards: " + str(len(legalcards)))

client = discord.Client()

async def post_card(card, channel):
  resp = string.Template("$name $mana_cost — $type — $legal").substitute(name=card.name, mana_cost=card.mana_cost if card.mana_cost else '', type=card.type, text=card.text, legal=":white_check_mark:" if card.name.lower().strip() in legalcards else ":no_entry_sign: (not legal in PD)", pt=str(card.power)+ "/" + str(card.toughness) if "Creature" in card.type else '')
  await client.send_message(channel, resp)
  filename = downloadimage(card.name, card.multiverse_id)
  if filename is None:
    await client.send_message(channel, card.text)
  else:
    await client.send_file(channel, filename)
  #if card.original_text != card.text:
  #  await client.send_message(channel, card.text)

async def post_cards(cards, channel):
  tmp = string.Template("$name $legal, ")
  text = ""
  images = ""
  for card in cards:
    text = text + tmp.substitute(name=card.name, legal=":white_check_mark:" if card.name.lower().strip() in legalcards else ":no_entry_sign:")
    images = images + "|" + escape(card.name)
  await client.send_message(channel, text.strip(", "))
  filename = downloadimage(images, 0)
  if filename is None:
    await client.send_message(channel, "No image available")
  else:
    await client.send_file(channel, filename)

@client.event
async def on_message(message):
  # we do not want the bot to reply to itself
  if message.author == client.user:
    return
  print(message.content)
  content = message.content
  end = len(content)
  start = content.find("[") + 1
  if "gatherer.wizards.com" in content.lower():
    return
  results = []
  while start > 0:
    end = content.find("]", start)
    search = content[start: end].strip('[ ').lower()
    print("Request : " + search)
    # Skip searching if the request is too short.
    if len(search) <= 2:
      return
    found = False
    cards = cardsearch(search)
    for card in cards:
      if found:
        break
      if card.type=="Vanguard":
        continue
      print(card.name.lower())
      if card.name.lower() == search:
        results.append(card)
        found = True
    # Search for something that starts with the query
    for card in cards:
      if found:
        break
      if card.type=="Vanguard":
        continue
      if card.name.lower().startswith(search):
        results.append(card)
        found = True
    # Search for the query anywhere in the name whatsoever
    for card in cards:
      if found:
        break
      if card.type=="Vanguard":
        continue
      results.append(card)
      found = True
    start = content.find("[", end) + 1
  if not found:
    return
  if len(results) > 1:
    await post_cards(results, message.channel)
  elif len(results) == 1:
    await post_card(results[0], message.channel)

@client.event
async def on_ready():
  print('Logged in as')
  print(client.user.name)
  print(client.user.id)
  print('------')
client.run(os.environ['TOKEN'])
