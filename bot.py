import collections
import hashlib
import os
import re
import random
import sys
import unicodedata
import urllib.parse

import discord

import config
import fetcher
import find
import oracle
import emoji

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
    legal_cards = fetcher.legal_cards()
    print("Legal cards: {0}".format(str(len(legal_cards))))
    oracle.update_legality(legal_cards)

def escape(str_input):
    # Expand 'AE' into two characters. This matches the legal list and
    # WotC's naming scheme in Kaladesh, and is compatible with the
    # image server and magidex.
    return '+'.join(urllib.parse.quote(cardname.replace(u'Æ', 'AE')) for cardname in str_input.split(' ')).lower()

def better_image(cards):
    c = '|'.join(card.name for card in cards)
    return "http://magic.bluebones.net/proxies/?c=" + escape(c)

def http_image(multiverse_id):
    return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(multiverse_id)    +'.jpg'

# Given a list of cards return one (aribtrarily) for each unique name in the list.
def uniqify_cards(cards):
    # Remove multiple printings of the same card from the result set.
    results = collections.OrderedDict()
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
        fetcher.store(better_image(cards), filepath)
    except fetcher.FetchException as e:
        print("Error: {0}".format(e))
    if acceptable_file(filepath):
        return filepath
    multiverse_id = cards[0].multiverse_id
    if multiverse_id and multiverse_id > 0:
        print("Trying to get fallback image for " + imagename)
        try:
            fetcher.store(http_image(multiverse_id), filepath)
        except fetcher.FetchException as e:
            print("HTTP Error: {0}".format(e))
        if acceptable_file(filepath):
            return filepath
    return None

def parse_queries(content):
    queries = re.findall(r'\[([^\]]*)\]', content)
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
    results = [card for card in cards if card.name.lower().startswith(query + " ") or card.name.lower().startswith(query + ",")]
    if len(results) > 0:
        return uniqify_cards(results)
    # If not found, use cards that start with the query.
    results = [card for card in cards if card.name.lower().startswith(query)]
    if len(results) > 0:
        return uniqify_cards(results)
    # If we didn't find any of those then use all search results.
    return uniqify_cards(cards)

def legal_emoji(card, verbose=False):
    if card.name.lower().strip() in legal_cards:
        return ':white_check_mark:'
    s = ':no_entry_sign:'
    if verbose:
        s += ' (not legal in PD)'
    return s

def complex_search(query):
    print("Searching for {0}".format(query))
    return find.search(query).fetchall()

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
        mana = emoji.replace_emoji(card.mana_cost, channel) or ''
        legal = legal_emoji(card, True)
        text = "{name} {mana_cost} — {type} — {legal}".format(name=card.name, mana_cost=mana, type=card.type, legal=legal)
    else:
        text = ', '.join("{name} {legal}".format(name=card.name, legal=legal_emoji(card)) for card in cards)
        text += more_text
    image_file = download_image(cards)
    await client.send_message(channel, text)
    if image_file is None:
        if len(cards) == 1:
            await client.send_message(channel, emoji.replace_emoji(cards[0].text))
        else:
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
        number = 1
        if len(message.content) > 7:
            try:
                number = int(message.content[7:].strip())
            except ValueError:
                pass
        cards = [oracle.search(random.choice(legal_cards))[0] for n in range(0, number)]
        await post_cards(cards, message.channel)
    elif message.content.startswith('!reload'):
        update_legality()
        await client.send_message(message.channel, 'Reloaded list of legal cards.')
    elif message.content.startswith('!restartbot'):
        sys.exit()
    elif message.content.startswith('!search '):
        q = message.content[len('!search '):]
        cards = complex_search(q)
        await post_cards(cards, message.channel)
        if len(cards) > 10:
            await client.send_message(message.channel, 'http://magidex.com/search/?q=' + escape(q))
    elif message.content.startswith('!status'):
        status = fetcher.mtgo_status()
        await client.send_message(message.channel, 'MTGO is {status}'.format(status=status))
    elif message.content.startswith('!echo'):
        s = message.content[len('!echo '):]
        s = emoji.replace_emoji(s, message.channel)
        print("Echoing {0}".format(s))
        await client.send_message(message.channel, s)
    elif message.content.startswith('!help'):
        msg = """Basic bot usage: Include [cardname] in your regular messages.
The bot will search for any quoted cards, and respond with the card details.

Addiional Commands:
`!search query` Search for cards, using a magidex style query.
`!random` Request a random PD legal card
`!random X` Request X random PD legal cards.
`!help` Get this message.

Have any Suggesions/Bug Reports? Submit them here: https://github.com/PennyDreadfulMTG/Penny-Dreadful-Discord-Bot/issues
Want to contribute? Send a Pull Request."""
        await client.send_message(message.channel, msg)
    elif message.content.startswith('!'):
        cmd = message.content.split(' ')[0]
        await client.send_message(message.channel, 'Unknown command `{cmd}`. Try `!help`?'.format(cmd=cmd))

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
