import collections
import datetime
import hashlib
import os
import random
import re
import sys
import unicodedata
import urllib.parse
from typing import List

import configuration
import emoji
import fetcher
from card import Card
from find import search
from oracle import Oracle

async def respond_to_card_names(message, bot):
    # Don't parse messages with Gatherer URLs because they use square brackets in the querystring.
    if 'gatherer.wizards.com' in message.content.lower():
        return
    queries = parse_queries(message.content)
    if len(queries) == 0:
        return
    cards = cards_from_queries(queries, bot.oracle)
    await bot.post_cards(cards, message.channel)

async def handle_command(message, bot):
    parts = message.content.split(' ', 1)
    cmd = parts[0].lstrip('!').lower()
    args = ""
    if len(parts) > 1:
        args = parts[1]

    method = [m for m in dir(Commands) if m == cmd]
    if len(method) > 0:
        method = getattr(Commands, method[0])
        if method.__code__.co_argcount == 5:
            await method(Commands, bot, message.channel, args, message.author)
        elif method.__code__.co_argcount == 4:
            await method(Commands, bot, message.channel, args)
        elif method.__code__.co_argcount == 3:
            await method(Commands, bot, message.channel)
        elif method.__code__.co_argcount == 2:
            await method(Commands, bot)
        elif method.__code__.co_argcount == 1:
            await method(Commands)
    else:
        await bot.client.send_message(message.channel, 'Unknown command `{cmd}`. Try `!help`?'.format(cmd=cmd))

class Commands:
    """To define a new command, simply add a new method to this class.
    If you want !help to show the message, add a docstring to the method.
    Method parameters should be in the format:
    `async def commandname(self, bot, channel, args, author)`
    Where any argument after self is optional. (Although at least channel is usually needed)
    """

    async def help(self, bot, channel):
        """`!help` Get this message."""
        msg = """Basic bot usage: Include [cardname] in your regular messages.
The bot will search for any quoted cards, and respond with the card details.

Addiional Commands:"""
        for methodname in dir(Commands):
            if methodname.startswith("__"):
                continue
            method = getattr(self, methodname)
            if method.__doc__:
                if not method.__doc__.startswith('`'):
                    msg += '\n`!{0}` {1}'.format(methodname, method.__doc__)
                else:
                    msg += '\n{0}'.format(method.__doc__)
        msg += """

Have any Suggesions/Bug Reports? Submit them here: https://github.com/PennyDreadfulMTG/Penny-Dreadful-Discord-Bot/issues
Want to contribute? Send a Pull Request."""
        await bot.client.send_message(channel, msg)

    async def random(self, bot, channel, args):
        """`!Random` Request a random PD legal card
`!random X` Request X random PD legal cards."""
        number = 1
        if len(args) > 0:
            try:
                number = int(args.strip())
            except ValueError:
                pass
        cards = [bot.oracle.search(random.choice(bot.legal_cards))[0] for n in range(0, number)]
        await bot.post_cards(cards, channel)

    async def p1p1(self, bot, channel):
        """`!p1p1` Request a random PD legal draft pack
`!random X` Request X random PD legal cards."""
        cards = [bot.oracle.search(random.choice(bot.legal_cards))[0] for n in range(0, 15)]
        await bot.client.send_message(channel, 'Pack 1, Pick 1 Game! If presented with this pack, what would you pick?')
        await bot.post_cards(cards, channel, "", False, False, True)

    async def update(self, bot, channel):
        bot.legal_cards = bot.oracle.get_legal_cards(True)
        await bot.client.send_message(channel, 'Reloaded list of legal cards.')

    async def restartbot(self, bot, channel):
        await bot.client.send_message(channel, 'Rebooting!')
        sys.exit()

    async def search(self, bot, channel, args, author):
        """`!search query` Search for cards, using a magidex style query."""
        cards = complex_search(args)
        if len(cards) == 0:
            await bot.client.send_message(channel, '{0}: No matches.'.format(author.mention))
            return
        additional_text = ''
        if len(cards) > 10:
            additional_text = 'http://magidex.com/search/?q=' + escape(args)
        await bot.post_cards(cards, channel, additional_text)

    async def bigsearch(self, bot, channel, args, author):
        """`!bigsearch` Show all the cards relating to a query. Large searches will be returned to you via PM."""
        cards = complex_search(args)
        if len(cards) == 0:
            await bot.client.send_message(channel, '{0}: No matches.'.format(author.mention))
            return
        if len(cards) > 10 and not channel.is_private:
            msg = "Search contains {n} cards.  Sending you the results through Private Message".format(n=len(cards))
            await bot.client.send_message(channel, msg)
            channel = author
        await bot.post_cards(cards, channel, verbose=True)

    async def status(self, bot, channel):
        """`!status` Gives the status of MTGO, UP or DOWN."""
        status = fetcher.mtgo_status()
        await bot.client.send_message(channel, 'MTGO is {status}'.format(status=status))

    async def echo(self, bot, channel, args):
        s = emoji.replace_emoji(args, channel)
        print('Echoing {s}'.format(s=s))
        await bot.client.send_message(channel, s)

    async def barbs(self, bot, channel):
        """`!barbs` Gives Volvary's helpful advice for when to sideboard in Aura Barbs."""
        msg = "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."
        await bot.client.send_message(channel, msg)

    async def quality(self, bot, channel):
        """A helpful reminder about everyone's favorite way to play digital Magic"""
        msg = "**Magic Online** is a Quality™ Program."
        await bot.client.send_message(channel, msg)

    async def rhinos(self, bot, channel):
        """Anything can be a rhino if you try hard enough"""
        rhinos = []
        rhinos.extend(cards_from_query("Siege Rhino", bot.oracle))
        rhinos.append(random.choice(complex_search('f:pd o:"copy of target creature"')))
        rhinos.append(random.choice(complex_search('f:pd o:"return target creature card from your graveyard to the battlefield"')))
        rhinos.append(random.choice(complex_search('f:pd o:"search your library for a creature"')))
        msg = "\nSo of course we have {rhino}.".format(rhino=rhinos[0].name)
        msg += " And we have {copy}. It can become a rhino, so that's a rhino.".format(copy=rhinos[1].name)
        msg += " Then there's {reanimate}. It can get back one of our rhinos, so that's a rhino.".format(reanimate=rhinos[2].name)
        msg += " And then we have {search}. It's a bit of a stretch, but that's a rhino too.".format(search=rhinos[3].name)
        await bot.post_cards(rhinos, channel, msg)

    async def rotation(self, bot, channel):
        standard = fetcher.whatsinstandard()
        for release in standard:
            reldate = datetime.datetime.strptime(release["enter_date"], "%Y-%m-%dT%H:%M:%S.%fZ")
            if reldate > datetime.datetime.now():
                diff = reldate - datetime.datetime.now()
                msg = "The next rotation is in {diff}".format(diff=diff)
                await bot.client.send_message(channel, msg)
                return


def escape(str_input) -> str:
    # Expand 'AE' into two characters. This matches the legal list and
    # WotC's naming scheme in Kaladesh, and is compatible with the
    # image server and magidex.
    return '+'.join(urllib.parse.quote(cardname.replace(u'Æ', 'AE')) for cardname in str_input.split(' ')).lower()

def better_image(cards) -> str:
    c = '|'.join(card.name for card in cards)
    return 'http://magic.bluebones.net/proxies/?c={c}'.format(c=escape(c))

def http_image(multiverse_id) -> str:
    return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(multiverse_id)    +'.jpg'

# Given a list of cards return one (aribtrarily) for each unique name in the list.
def uniqify_cards(cards):
    # Remove multiple printings of the same card from the result set.
    results = collections.OrderedDict()
    for card in cards:
        results[card.name.lower()] = card
    return results.values()

def acceptable_file(filepath: str) -> bool:
    return os.path.isfile(filepath) and os.path.getsize(filepath) > 0

def basename(cards):
    return '_'.join(re.sub('[^a-z-]', '-', unaccent(card.name).lower()) for card in cards)

def unaccent(s):
    return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

def download_image(cards: List[Card], oracle: Oracle) -> str:
    imagename = basename(cards)
    # Hash the filename if it's otherwise going to be too large to use.
    if len(imagename) > 240:
        imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
    filename = imagename + '.jpg'
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename=filename)
    if acceptable_file(filepath):
        return filepath
    print('Trying to get first choice image for {cards}'.format(cards=', '.join(card.name for card in cards)))
    try:
        fetcher.store(better_image(cards), filepath)
    except fetcher.FetchException as e:
        print('Error: {e}'.format(e=e))
    if acceptable_file(filepath):
        return filepath
    print(oracle)
    print(oracle.get_printings(cards[0]))
    printings = oracle.get_printings(cards[0])
    if len(printings) > 0:
        multiverse_id = printings[0].multiverseid
        if multiverse_id and int(multiverse_id) > 0:
            print('Trying to get fallback image for {imagename}'.format(imagename=imagename))
            try:
                fetcher.store(http_image(multiverse_id), filepath)
            except fetcher.FetchException as e:
                print('Error: {e}'.format(e=e))
            if acceptable_file(filepath):
                return filepath
    return None

def parse_queries(content: str) -> List[str]:
    queries = re.findall(r'\[([^\]]*)\]', content)
    return [query.lower() for query in queries]

def cards_from_queries(queries, oracle):
    all_cards = []
    for query in queries:
        cards = cards_from_query(query, oracle)
        if len(cards) > 0:
            all_cards.extend(cards)
    return all_cards

def cards_from_query(query, oracle):
    # Skip searching if the request is too short.
    if len(query) <= 2:
        return []
    cards = oracle.search(query)
    cards = [card for card in cards if card.type != 'Vanguard' and card.layout != 'token']
    # First look for an exact match.
    for card in cards:
        if (card.name.lower() == query) or ((card.alias is not None) and (card.alias.lower() == query)):
            return [card]
    # If not found, use cards that start with the query and a punctuation char.
    results = [card for card in cards if card.name.lower().startswith('{query} '.format(query=query)) or card.name.lower().startswith('{query},'.format(query=query))]
    if len(results) > 0:
        return uniqify_cards(results)
    # If not found, use cards that start with the query.
    results = [card for card in cards if card.name.lower().startswith(query)]
    if len(results) > 0:
        return uniqify_cards(results)
    # If we didn't find any of those then use all search results.
    return uniqify_cards(cards)

def legal_emoji(card, legal_cards, verbose=False):
    if card.name.lower().strip() in legal_cards:
        return ':white_check_mark:'
    s = ':no_entry_sign:'
    if verbose:
        s += ' (not legal in PD)'
    return s

def complex_search(query):
    if query == '':
        return []
    print('Searching for {query}'.format(query=query))
    return search.search(query)
