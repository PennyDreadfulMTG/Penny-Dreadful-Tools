import collections
import datetime
import glob
import logging
import os
import random
import re
import subprocess
import textwrap
import time
import traceback
from copy import copy
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import inflect
from discord import FFmpegPCMAudio, File
from discord.channel import TextChannel
from discord.client import Client
from discord.member import Member
from discord.message import Message
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from discordbot import emoji
from magic import (card, database, fetcher, image_fetcher, multiverse, oracle,
                   rotation, tournaments)
from magic.models.card import Card
from magic.whoosh_search import SearchResult, WhooshSearcher
from shared import configuration, dtutil, repo
from shared.lazy import lazy_property
from shared.pd_exception import TooFewItemsException

DEFAULT_CARDS_SHOWN = 4
MAX_CARDS_SHOWN = 10
DISAMBIGUATION_EMOJIS = [':one:', ':two:', ':three:', ':four:', ':five:']
DISAMBIGUATION_EMOJIS_BY_NUMBER = {1 : '1⃣', 2 : '2⃣', 3 : '3⃣', 4 : '4⃣', 5 : '5⃣'}
DISAMBIGUATION_NUMBERS_BY_EMOJI = {'1⃣' : 1, '2⃣' : 2, '3⃣' : 3, '4⃣' : 4, '5⃣' : 5}

@lazy_property
def searcher() -> WhooshSearcher:
    return WhooshSearcher()

async def respond_to_card_names(message: Message, client: Client) -> None:
    # Don't parse messages with Gatherer URLs because they use square brackets in the querystring.
    if 'gatherer.wizards.com' in message.content.lower():
        return
    queries = parse_queries(message.content)
    if len(queries) > 0:
        async with message.channel.typing():
            results = results_from_queries(queries)
            cards = []
            for i in results:
                (r, mode) = i
                if r.has_match() and not r.is_ambiguous():
                    cards.extend(cards_from_names_with_mode([r.get_best_match()], mode))
                elif r.is_ambiguous():
                    cards.extend(cards_from_names_with_mode(r.get_ambiguous_matches(), mode))
        await post_cards(client, cards, message.channel, message.author)

    matches = re.findall(r'https?://(?:www.)?tappedout.net/mtg-decks/(?P<slug>[\w-]+)/?', message.content, flags=re.IGNORECASE)
    for match in matches:
        data = {'url': 'https://tappedout.net/mtg-decks/{slug}'.format(slug=match)}
        fetcher.internal.post(fetcher.decksite_url('/add/'), data)

async def handle_command(message: Message, client: Client) -> None:
    parts = message.content.split(' ', 1)
    method = find_method(parts[0])
    args = ''
    if len(parts) > 1:
        args = parts[1].strip()
    if method is not None:
        try:
            async with message.channel.typing():
                pass
            await method(Commands, client=client, channel=message.channel, args=args, author=message.author)
        except Exception as e: # pylint: disable=broad-except
            print('Caught exception processing command `{cmd}`'.format(cmd=message.content))
            tb = traceback.format_exc()
            print(tb)
            await message.channel.send('{author}: I know the command `{cmd}` but encountered an error while executing it.'.format(cmd=parts[0], author=message.author.mention))
            await getattr(Commands, 'bug')(Commands, channel=message.channel, args='Command failed with {c}: {cmd}\n\n```\n{tb}\n```'.format(c=e.__class__.__name__, cmd=message.content, tb=tb), author=message.author)

def find_method(name: str) -> Optional[Callable]:
    cmd = name.lstrip('!').lower()
    if len(cmd) == 0:
        return None
    method = [m for m in dir(Commands) if m in (cmd, '_' + cmd)]
    if len(method) == 0:
        method = [m for m in dir(Commands) if m.startswith(cmd) or m.startswith('_{cmd}'.format(cmd=cmd))]
    if len(method) > 0:
        return getattr(Commands, method[0])
    return None

def build_help(readme: bool = False, cmd: str = None) -> str:
    def print_group(group: str) -> str:
        msg = ''
        for methodname in dir(Commands):
            if methodname.startswith('__'):
                continue
            method = getattr(Commands, methodname)
            if getattr(method, 'group', None) != group:
                continue
            msg += '\n' + print_cmd(method, readme)
        return msg

    def print_cmd(method: Callable, verbose: bool) -> str:
        if method.__doc__:
            if not method.__doc__.startswith('`'):
                return '`!{0}` {1}'.format(method.__name__, method.__doc__)
            return '{0}'.format(method.__doc__)
        if verbose:
            return '`!{0}` No Help Available'.format(method.__name__)
        return '`!{0}`'.format(method.__name__)

    if cmd:
        method = find_method(cmd)
        if method:
            return print_cmd(method, True)
        return '`{cmd}` is not a valid command.'.format(cmd=cmd)

    msg = print_group('Commands')
    if readme:
        msg += '\n# Aliases'
        msg += print_group('Aliases')
        msg += '\n# Developer Commands'
        msg += print_group('Developer')
    return msg

def cmd_header(group: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        setattr(func, 'group', group)
        return func
    return decorator



# pylint: disable=too-many-public-methods
class Commands:
    """To define a new command, simply add a new method to this class.
    If you want !help to show the message, add a docstring to the method.
    Method parameters should be in the format:
    `async def commandname(self, client, channel, args, author)`
    Where any argument after self is optional. (Although at least channel is usually needed)
    """

    @cmd_header('Commands')
    async def help(self, channel: TextChannel, args: str, **_: Dict[str, Any]) -> None:
        """`!help` Provides information on how to operate the bot."""
        if args:
            msg = build_help(cmd=args)
        else:
            msg = """[cardname] to get card details.
"""
            msg += build_help()
            msg += """

Suggestions/bug reports: <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Discord-Bot/issues/>

Want to contribute? Send a Pull Request."""
        if len(msg) > 2000:
            await channel.send(msg[0:1999] + '…')
        else:
            await channel.send(msg)

    @cmd_header('Commands')
    async def random(self, client: Client, channel: TextChannel, args: str, **_: Dict[str, Any]) -> None:
        """`!random` Request a random PD legal card.
`!random X` Request X random PD legal cards."""
        number = 1
        additional_text = ''
        if len(args) > 0:
            try:
                number = int(args)
                if number > 10:
                    additional_text = "{number}? Tsk. Here's ten.".format(number=number)
                    number = 10
            except ValueError:
                pass
        cards = [oracle.cards_by_name()[name] for name in random.sample(oracle.legal_cards(), number)]
        await post_cards(client, cards, channel, None, additional_text)

    @cmd_header('Developer')
    async def update(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """Forces an update to legal cards and bugs."""
        oracle.legal_cards(force=True)
        multiverse.update_bugged_cards()
        multiverse.update_cache()
        multiverse.reindex()
        oracle.init(force=True)
        await channel.send('Reloaded legal cards and bugs.')

    @cmd_header('Developer')
    async def restartbot(self, client: Client, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """Restarts the bot."""
        await channel.send('Rebooting!')
        await client.logout()

    @cmd_header('Commands')
    async def search(self, client: Client, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!search {query}` Search for cards, using a scryfall-style query."""
        how_many, cardnames = fetcher.search_scryfall(args)
        cbn = oracle.cards_by_name()
        cards = [cbn[name] for name in cardnames if cbn.get(name) is not None]
        await post_cards(client, cards, channel, author, more_results_link(args, how_many))

    @cmd_header('Aliases')
    async def scryfall(self, client: Client, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!scryfall {query}` Alias for `!search`."""
        # Because of the weird way we call and use methods on Commands we need …
        # pylint: disable=too-many-function-args
        await self.search(self, client, channel, args, author)

    @cmd_header('Commands')
    async def status(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """`!status` Gives the status of Magic Online: UP or DOWN."""
        status = await fetcher.mtgo_status()
        await channel.send('MTGO is {status}'.format(status=status))

    @cmd_header('Developer')
    async def echo(self, client: Client, channel: TextChannel, args: str, **_: Dict[str, Any]) -> None:
        """Repeat after me…"""
        s = emoji.replace_emoji(args, client)
        await channel.send(s)

    @cmd_header('Commands')
    async def barbs(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """`!barbs` Gives Volvary's helpful advice for when to sideboard in Aura Barbs."""
        msg = "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."
        await channel.send(msg)

    @cmd_header('Commands')
    async def quality(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """`!quality` A helpful reminder about everyone's favorite way to play digital Magic"""
        msg = '**Magic Online** is a Quality™ Program.'
        await channel.send(msg)

    @cmd_header('Commands')
    async def rhinos(self, client: Client, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """`!rhinos` Anything can be a rhino if you try hard enough"""
        rhinos = []
        rhino_name = 'Siege Rhino'
        if random.random() < 0.05:
            rhino_name = 'Abundant Maw'
        rhinos.extend([oracle.cards_by_name()[rhino_name]])
        def find_rhino(query: str) -> Card:
            cards = complex_search('f:pd {0}'.format(query))
            if len(cards) == 0:
                cards = complex_search(query)
            return random.choice(cards)
        rhinos.append(find_rhino('o:"copy of target creature"'))
        rhinos.append(find_rhino('o:"return target creature card from your graveyard to the battlefield"'))
        rhinos.append(find_rhino('o:"search your library for a creature"'))
        msg = '\nSo of course we have {rhino}.'.format(rhino=rhinos[0].name)
        msg += " And we have {copy}. It can become a rhino, so that's a rhino.".format(copy=rhinos[1].name)
        msg += " Then there's {reanimate}. It can get back one of our rhinos, so that's a rhino.".format(reanimate=rhinos[2].name)
        msg += " And then we have {search}. It's a bit of a stretch, but that's a rhino too.".format(search=rhinos[3].name)
        await post_cards(client, rhinos, channel, additional_text=msg)

    @cmd_header('Commands')
    async def rotation(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """`!rotation` Give the date of the next Penny Dreadful rotation."""
        await channel.send(rotation.text())

    @cmd_header('Commands')
    async def rulings(self, client: Client, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!rulings {name}` Display rulings for a card."""
        await single_card_text(client, channel, args, author, card_rulings, 'rulings')

    @cmd_header('Commands')
    async def _oracle(self, client: Client, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!oracle {name}` Give the Oracle text of the named card."""
        await single_card_text(client, channel, args, author, oracle_text, 'oracle')

    @cmd_header('Commands')
    async def price(self, client: Client, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!price {name}` Get price information about the named card."""
        await single_card_text(client, channel, args, author, fetcher.card_price_string, 'price')

    @cmd_header('Commands')
    async def legal(self, client: Client, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """Announce whether the specified card is legal or not."""
        await single_card_text(client, channel, args, author, lambda c: '', 'legal')

    @cmd_header('Commands')
    async def modofail(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """Ding!"""
        if args.lower() == 'reset':
            self.modofail.count = 0
        if hasattr(author, 'voice') and author.voice is not None and author.voice.voice_channel is not None:
            voice_channel = author.voice.voice_channel
            voice = channel.server.voice_client
            if voice is None:
                voice = await voice_channel.connect()
            elif voice.channel != voice_channel:
                voice.move_to(voice_channel)
            voice.play(FFmpegPCMAudio('ding.ogg'))
        if time.time() > self.modofail.last_fail + 60 * 60:
            self.modofail.count = 0
        self.modofail.count += 1
        self.modofail.last_fail = time.time()
        await channel.send(':bellhop: **MODO fail** {0}'.format(self.modofail.count))
    modofail.count = 0
    modofail.last_fail = time.time()

    @cmd_header('Commands')
    async def resources(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!resources {args}` Link to useful pages related to `args`. Examples: 'tournaments', 'card Hymn to Tourach', 'deck check', 'league'."""
        results = {}
        if len(args) > 0:
            results.update(resources_resources(args))
            results.update(site_resources(args))
        s = ''
        if len(results) == 0:
            s = 'PD resources: <{url}>'.format(url=fetcher.decksite_url('/resources/'))
        elif len(results) > 10:
            s = '{author}: Too many results, please be more specific.'.format(author=author.mention)
        else:
            for url, text in results.items():
                s += '{text}: <{url}>\n'.format(text=text, url=url)
        await channel.send(s)

    @cmd_header('Developer')
    async def clearimagecache(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """Deletes all the cached images.  Use sparingly"""
        image_dir = configuration.get('image_dir')
        if not image_dir:
            return await channel.send('Cowardly refusing to delete from unknown image_dir.')
        files = glob.glob('{dir}/*.jpg'.format(dir=image_dir))
        for file in files:
            os.remove(file)
        await channel.send('{n} cleared.'.format(n=len(files)))

    @cmd_header('Developer')
    async def notpenny(self, channel: TextChannel, args: str, **_: Dict[str, Any]) -> None:
        """Don't show PD Legality in this channel"""
        existing = configuration.get_list('not_pd')
        if args == 'server' and getattr(channel, 'guild', None) is not None:
            cid = channel.guild.id
        else:
            cid = channel.id
        if str(cid) not in existing:
            existing.append(str(cid))
            configuration.write('not_pd', set(existing))
        if args == 'server':
            await channel.send('Disable PD legality marks for the entire server')
        else:
            await channel.send('Disable PD legality marks for this channel. If you wanted to disable for the entire server, use `!notpenny server` instead.')

    @cmd_header('Commands')
    async def bug(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """Report a bug/task for the Penny Dreadful Tools team. For Magic Online bugs see `!modobug`."""
        issue = repo.create_issue(args, author)
        if issue is None:
            await channel.send('Report issues at <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/new>')
        else:
            await channel.send('Issue has been reported at <{url}>'.format(url=issue.html_url))

    @cmd_header('Commands')
    async def modobug(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """Report a Magic Online bug."""
        await channel.send('Report Magic Online issues at <https://github.com/PennyDreadfulMTG/modo-bugs/issues/new>. Please follow the instructions there. Thanks!')

    @cmd_header('Commands')
    async def gbug(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """Report a Gatherling bug."""
        issue = repo.create_issue(args, author, 'Discord', 'PennyDreadfulMTG/gatherling')
        if issue is None:
            await channel.send('Report Gatherling issues at <https://github.com/PennyDreadfulMTG/gatherling/issues/new>')
        else:
            await channel.send('Issue has been reported at <{url}>.'.format(url=issue.html_url))

    @cmd_header('Commands')
    async def buglink(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) ->  None:
        """Get a link to the modo-bugs page for the named card."""
        base_url = 'https://github.com/PennyDreadfulMTG/modo-bugs/issues'
        if args == '':
            await channel.send(base_url)
            return
        result, mode = results_from_queries([args])[0]
        if result.has_match() and not result.is_ambiguous():
            c = cards_from_names_with_mode([result.get_best_match()], mode)[0]
            msg = '{base_url}?utf8=%E2%9C%93&q=is%3Aissue+is%3Aopen+%22{name}%22'.format(base_url=base_url, name=fetcher.internal.escape(args))
            if not c.bugs or len(c.bugs) == 0:
                msg = "I don't know of a bug for {name} but here's the link: {link}".format(name=c.name, link=msg)
        else:
            msg = "{author}: I'm not quite sure what you mean by '{args}'".format(author=author.mention, args=args)
        await channel.send(msg)

    @cmd_header('Commands')
    async def invite(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """Invite me to your server."""
        await channel.send('Invite me to your discord server by clicking this link: <https://discordapp.com/oauth2/authorize?client_id=224755717767299072&scope=bot&permissions=268757056>')

    @cmd_header('Commands')
    async def spoiler(self, client: Client, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!spoiler {cardname}`: Request a card from an upcoming set."""
        if len(args) == 0:
            return await channel.send('{author}: Please specify a card name.'.format(author=author.mention))
        sfcard = fetcher.internal.fetch_json('https://api.scryfall.com/cards/named?fuzzy={name}'.format(name=args))
        if sfcard['object'] == 'error':
            return await channel.send('{author}: {details}'.format(author=author.mention, details=sfcard['details']))
        imagename = '{set}_{number}'.format(set=sfcard['set'], number=sfcard['collector_number'])
        imagepath = '{image_dir}/{imagename}.jpg'.format(image_dir=configuration.get('image_dir'), imagename=imagename)
        if sfcard.get('card_faces') and sfcard.get('layout', '') != 'split':
            c = sfcard['card_faces'][0]
        else:
            c = sfcard
        fetcher.internal.store(c['image_uris']['normal'], imagepath)
        text = emoji.replace_emoji('{name} {mana}'.format(name=sfcard['name'], mana=c['mana_cost']), client)
        await channel.send(file=File(imagepath), content=text)
        oracle.scryfall_import(sfcard['name'])

    @cmd_header('Commands')
    async def time(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!time {location}` Show the current time in the specified location."""
        try:
            t = fetcher.time(args)
        except TooFewItemsException:
            logging.exception('Exception trying to get the time for %s.', args)
            return await channel.send('{author}: Location not found.'.format(author=author.mention))
        await channel.send('{args}: {time}'.format(args=args, time=t))

    @cmd_header('Commands')
    async def pdm(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """Alias for `!resources`."""
        # Because of the weird way we call and use methods on Commands we need …
        # pylint: disable=too-many-function-args
        await self.resources(self, channel, args, author)

    @cmd_header('Commands')
    async def google(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!google {args}` Search google for `args`."""
        api_key = configuration.get('cse_api_key')
        cse_id = configuration.get('cse_engine_id')
        if api_key is None or cse_id is None:
            return await channel.send('The google command has not been configured.')

        if len(args) == 0:
            return await channel.send('{author}: No search term provided. Please type !google followed by what you would like to search'.format(author=author.mention))

        try:
            service = build('customsearch', 'v1', developerKey=api_key)
            res = service.cse().list(q=args, cx=cse_id, num=1).execute() # pylint: disable=no-member
            if 'items' in res:
                r = res['items'][0]
                s = '{title} <{url}> {abstract}'.format(title=r['title'], url=r['link'], abstract=r['snippet'])
            else:
                s = '{author}: Nothing found on Google.'.format(author=author.mention)
        except HttpError as e:
            if e.resp['status'] == '403':
                s = 'We have reached the allowed limits of Google API'
            else:
                raise e

        await channel.send(s)

    @cmd_header('Commands')
    async def tournament(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """`!tournament` Get information about the next tournament."""
        t = tournaments.next_tournament_info()
        prev = tournaments.previous_tournament_info()
        if prev['near']:
            started = 'it started '
        else:
            started = ''
        prev_message = 'The last tournament was {name}, {started}{time} ago'.format(name=prev['next_tournament_name'], started=started, time=prev['next_tournament_time'])
        next_time = 'in ' + t['next_tournament_time'] if t['next_tournament_time'] != dtutil.display_time(0, 0) else t['next_tournament_time']
        await channel.send('The next tournament is {name} {next_time}.\nSign up on <http://gatherling.com/>\nMore information: {url}\n{prev_message}'.format(name=t['next_tournament_name'], next_time=next_time, prev_message=prev_message, url=fetcher.decksite_url('/tournaments/')))

    @cmd_header('Commands')
    async def art(self, channel: TextChannel, args: str, author: Member, **_: Dict[str, Any]) -> None:
        """`!art {name}` Display the art (only) of the most recent printing of the named card."""
        if not args:
            return await channel.send('{author}: Please specify a card name.'.format(author=author.mention))
        c = await single_card_or_send_error(channel, args, author, 'art')
        if c is not None:
            file_path = re.sub('.jpg$', '.art_crop.jpg', image_fetcher.determine_filepath([c]))
            if image_fetcher.download_scryfall_card_image(c, file_path, version='art_crop'):
                await send_image_with_retry(channel, file_path)
            else:
                await channel.send('{author}: Could not get image.'.format(author=author.mention))

    @cmd_header('Commands')
    async def explain(self, channel: TextChannel, args: str, **_: Dict[str, Any]) -> None:
        """`!explain`. Get a list of things the bot knows how to explain.
`!explain {thing}`. Print commonly needed explanation for 'thing'."""
        num_tournaments = inflect.engine().number_to_words(len(tournaments.all_series_info()))
        explanations: Dict[str, Tuple[str, Dict[str, str]]] = {
            'bugs': (
                'We keep track of cards that are bugged on Magic Online. We allow the playing of cards with known bugs in Penny Dreadful under certain conditions. See the full rules on the website.',
                {
                    'Known Bugs List': fetcher.decksite_url('/bugs/'),
                    'Tournament Rules': fetcher.decksite_url('/tournaments/#bugs'),
                    'Bugged Cards Database': 'https://github.com/PennyDreadfulMTG/modo-bugs/issues/'
                }

            ),
            'deckbuilding': (
                """
                The best way to build decks is to use a search engine that supports Penny Dreadful legality (`f:pd`) like Scryfall.
                You can find Penny Dreadful decklists from tournaments, leagues and elsewhere at pennydreadfulmagic.com.
                """,
                {
                    'Scryfall': 'https://scryfall.com/',
                    'Latest Decks': fetcher.decksite_url('/'),
                    'Legal Cards List': 'http://pdmtgo.com/legal_cards.txt'
                }
            ),
            'decklists': (
                """
                You can find Penny Dreadful decklists from tournaments, leagues and elsewhere at pennydreadfulmagic.com
                """,
                {
                    'Latest Decks': fetcher.decksite_url('/')
                }
            ),
            'doorprize': (
                "The door prize is 1 tik credit with Cardhoarder, awarded to one randomly-selected player that completes the Swiss rounds but doesn't make top 8.",
                {}
            ),
            'league': (
                """
                Leagues last for roughly a month. You may enter any number of times but only one deck at a time.
                You play five matches per run. You can join the league at any time.
                To find a game sign up and then create a game in Just for Fun with "Penny Dreadful League" as the comment.
                Top 8 finishers on each month's league leaderboard win credit with MTGO Traders.
                When you complete a five match league run for the first time ever you will get 1 tik credit with MTGO Traders.
                """,
                {
                    'More Info': fetcher.decksite_url('/league/'),
                    'Sign Up': fetcher.decksite_url('/signup/'),
                    'Current League': fetcher.decksite_url('/league/current/')
                }
            ),
            'legality': (
                """
                Legality is set at the release of a Standard-legal set on Magic Online.
                Prices are checked every hour for a week beforehand. Anything 1c or less for half or more of all checks is legal for the season.
                Cards from the just-released set are added (nothing removed) three weeks later via a supplemental rotation after prices have settled a little.
                Any version of a card on the legal cards list is legal.
                """,
                {
                    'Deck Checker': 'http://pdmtgo.com/deck_check.html',
                    'Legal Cards List': 'http://pdmtgo.com/legal_cards.txt',
                    'Rotation Speculation': fetcher.decksite_url('/rotation/speculation/'),
                    'Rotation Changes': fetcher.decksite_url('/rotation/changes/')
                }
            ),
            'noshow': (
                """
                If your opponent does not join your game please @-message them on Discord and contact them on Magic Online.
                If you haven't heard from them by 10 minutes after the start of the round let the Tournament Organizer know.
                You will receive a 2-0 win and your opponent will be dropped from the competition.
                """,
                {}
            ),
            'playing': (
                """
                To get a match go to Constructed Open Play, Just for Fun on MTGO and create a Freeform game with "Penny Dreadful" in the comments.
                """,
                {}
            ),
            'prices': (
                """
                The price output contains current price.
                If the price is low enough it will show season-low and season-high also.
                If the card has been 1c at any point this season it will also include the amount of time (as a percentage) the card has spent at 1c or below this week, month and season.
                """,
                {}
            ),
            'prizes': (
                """
                Gatherling tournaments pay prizes to the Top 8 in Cardhoarder credit.
                This credit will appear when you trade with one of their bots on Magic Online.
                One player not making Top 8 but playing all the Swiss rounds will be randomly allocated the door prize.
                Prizes are credited once a week usually on the Friday or Saturday following the tournament but may sometimes take longer.
                """,
                {
                    'More Info': fetcher.decksite_url('/tournaments/')
                }
            ),
            'report': (
                """
                For gatherling.com tournaments PDBot is information-only, *both* players must report near the top of Player CP.
                If PDBot reports your league match in Discord you don't need to do anything (only league matches, tournament matches must still be reported). If not, either player can report.
                """,
                {
                    'Gatherling': 'https://gatherling.com/player.php',
                    'League Report': fetcher.decksite_url('/report/')
                }
            ),
            'retire': (
                'To retire from a league run message PDBot on MTGO with `!retire`. If you have authenticated with Discord on pennydreadfulmagic.com you can say `!retire` on Discord or retire on the website.',
                {
                    'Retire': fetcher.decksite_url('/retire/')
                }
            ),
            'spectating': (
                """
                Spectating tournament and league matches is allowed and encouraged.
                Please do not write anything in chat except to call PDBot's `!record` command to find out the current score in games.
                """,
                {}
            ),
            'tournament': (
                """
                We have {num_tournaments} free-to-enter weekly tournaments that award trade credit prizes from Cardhoarder.
                They are hosted on gatherling.com along with a lot of other player-run Magic Online events.
                """.format(num_tournaments=num_tournaments),
                {
                    'More Info': fetcher.decksite_url('/tournaments/'),
                    'Sign Up': 'https://gatherling.com/',
                }
            ),
            'username': (
                """
                Please change your Discord username to include your MTGO username so we can know who you are.
                To change, right-click your username.
                This will not affect any other Discord channel.
                """,
                {}
            )
        }
        keys = sorted(explanations.keys())
        explanations['drop'] = explanations['retire']
        explanations['rotation'] = explanations['legality']
        explanations['spectate'] = explanations['spectating']
        explanations['tournaments'] = explanations['tournament']
        explanations['watching'] = explanations['spectating']
        explanations['spectate'] = explanations['spectating']
        word = args.lower().replace(' ', '').rstrip('s') # strip trailing 's' to make 'leagues' match 'league' and simliar without affecting the output of `!explain` to be unnecessarily plural.
        if len(word) > 0:
            for k in explanations:
                if k.startswith(word):
                    word = k
        try:
            s = '{text}\n'.format(text=textwrap.dedent(explanations[word][0]))
        except KeyError:
            usage = 'I can explain any of these things: {things}'.format(things=', '.join(sorted(keys)))
            return await channel.send(usage)
        for k in sorted(explanations[word][1].keys()):
            s += '{k}: <{v}>\n'.format(k=k, v=explanations[word][1][k])
        await channel.send(s)

    @cmd_header('Developer')
    async def version(self, channel: TextChannel, **_: Dict[str, Any]) -> None:
        """Display the current version numbers"""
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], universal_newlines=True).strip('\n').strip('"')
        mtgjson = database.mtgjson_version()
        return await channel.send('I am currently running mtgbot version `{commit}`, and mtgjson version `{mtgjson}`'.format(commit=commit, mtgjson=mtgjson))

# Given a list of cards return one (aribtrarily) for each unique name in the list.
def uniqify_cards(cards: List[Card]) -> List[Card]:
    # Remove multiple printings of the same card from the result set.
    results: Dict[str, Card] = collections.OrderedDict()
    for c in cards:
        results[card.canonicalize(c.name)] = c
    return list(results.values())

def parse_queries(content: str) -> List[str]:
    queries = re.findall(r'\[?\[([^\]]*)\]\]?', content)
    return [card.canonicalize(query) for query in queries if len(query) > 2]

def cards_from_names_with_mode(cards: Sequence[Optional[str]], mode: str) -> List[Card]:
    oracle_cards = oracle.cards_by_name()
    return [copy_with_mode(oracle_cards[c], mode) for c in cards if c is not None]

def copy_with_mode(oracle_card: Card, mode: str) -> Card:
    c = copy(oracle_card)
    c['mode'] = mode
    return c

def parse_mode(query: str) -> List[str]:
    mode = ''
    if query.startswith('$'):
        mode = '$'
        query = query[1:]
    return [mode, query]

def results_from_queries(queries: List[str]) -> List[Tuple[SearchResult, str]]:
    all_results = []
    for query in queries:
        mode, query = parse_mode(query)
        result = searcher().search(query)
        all_results.append((result, mode))
    return all_results

def complex_search(query: str) -> List[Card]:
    if query == '':
        return []
    _, cardnames = fetcher.search_scryfall(query)
    cbn = oracle.cards_by_name()
    return [cbn[name] for name in cardnames if cbn.get(name) is not None]

def roughly_matches(s1: str, s2: str) -> bool:
    return simplify_string(s1).find(simplify_string(s2)) >= 0

def simplify_string(s: str) -> str:
    s = ''.join(s.split())
    return re.sub(r'[\W_]+', '', s).lower()

def disambiguation(cards: List[str]) -> str:
    if len(cards) > 5:
        return ','.join(cards)
    return ' '.join([' '.join(x) for x in zip(DISAMBIGUATION_EMOJIS, cards)])

async def disambiguation_reactions(message: Message, cards: List[str]) -> None:
    for i in range(1, len(cards)+1):
        await message.add_reaction(DISAMBIGUATION_EMOJIS_BY_NUMBER[i])

async def single_card_or_send_error(channel: TextChannel, args: str, author: Member, command: str) -> Optional[Card]:
    result, mode = results_from_queries([args])[0]
    if result.has_match() and not result.is_ambiguous():
        return cards_from_names_with_mode([result.get_best_match()], mode)[0]

    if result.is_ambiguous():
        message = await channel.send('{author}: Ambiguous name for {c}. Suggestions: {s}'.format(author=author.mention, c=command, s=disambiguation(result.get_ambiguous_matches()[0:5])))
        await disambiguation_reactions(message, result.get_ambiguous_matches()[0:5])
    else:
        await channel.send('{author}: No matches.'.format(author=author.mention))
    return None

# pylint: disable=too-many-arguments
async def single_card_text(client: Client, channel: TextChannel, args: str, author: Member, f: Callable, command: str) -> None:
    c = await single_card_or_send_error(channel, args, author, command)
    if c is not None:
        legal_emoji = emoji.legal_emoji(c)
        text = emoji.replace_emoji(f(c), client)
        message = '**{name}** {legal_emoji} {text}'.format(name=c.name, legal_emoji=legal_emoji, text=text)
        await channel.send(message)

def oracle_text(c: Card) -> str:
    return c.text

def card_rulings(c: Card) -> str:
    raw_rulings = fetcher.rulings(c.name)
    rulings = [r['comment'] for r in raw_rulings]
    if len(rulings) > 3:
        n = len(rulings) - 2
        rulings = rulings[:2]
        rulings.append('And {n} others.  See <https://scryfall.com/search?q=%21%22{cardname}%22#rulings>'.format(n=n, cardname=fetcher.internal.escape(c.name)))
    return '\n'.join(rulings) or 'No rulings available.'

def site_resources(args: str) -> Dict[str, str]:
    results = {}
    match = re.match('^s? ?([0-9]*|all) +', args)
    if match:
        season_prefix = 'seasons/' + match.group(1)
        args = args.replace(match.group(0), '', 1).strip()
    else:
        season_prefix = ''
    if ' ' in args:
        area, detail = args.split(' ', 1)
    else:
        area, detail = args, ''
    if area == 'archetype':
        area = 'archetypes'
    if area == 'card':
        area = 'cards'
    if area == 'person':
        area = 'people'
    sitemap = fetcher.sitemap()
    matches = [endpoint for endpoint in sitemap if endpoint.startswith('/{area}/'.format(area=area))]
    if len(matches) > 0:
        detail = '{detail}/'.format(detail=fetcher.internal.escape(detail, True)) if detail else ''
        url = fetcher.decksite_url('{season_prefix}/{area}/{detail}'.format(season_prefix=season_prefix, area=fetcher.internal.escape(area), detail=detail))
        results[url] = args
    return results

def resources_resources(args: str) -> Dict[str, str]:
    results = {}
    words = args.split()
    resources = fetcher.resources()
    for title, items in resources.items():
        for text, url in items.items():
            asked_for_this_section_only = len(words) == 1 and roughly_matches(title, words[0])
            asked_for_this_section_and_item = len(words) == 2 and roughly_matches(title, words[0]) and roughly_matches(text, words[1])
            asked_for_this_item_only = len(words) == 1 and roughly_matches(text, words[0])
            the_whole_thing_sounds_right = roughly_matches(text, ' '.join(words))
            the_url_matches = roughly_matches(url, ' '.join(words))
            if asked_for_this_section_only or asked_for_this_section_and_item or asked_for_this_item_only or the_whole_thing_sounds_right or the_url_matches:
                results[url] = text
    return results

def more_results_link(args: str, total: int) -> str:
    return 'and {n} more.\n<https://scryfall.com/search/?q={q}>'.format(n=total - 4, q=fetcher.internal.escape(args)) if total > MAX_CARDS_SHOWN else ''

async def post_cards(
        client: Client,
        cards: List[Card],
        channel: TextChannel,
        replying_to: Optional[Member] = None,
        additional_text: str = ''
) -> None:
    if len(cards) == 0:
        await post_no_cards(channel, replying_to)
        return
    not_pd = configuration.get_list('not_pd')
    disable_emoji = str(channel.id) in not_pd or (getattr(channel, 'guild', None) is not None and str(channel.guild.id) in not_pd)
    cards = uniqify_cards(cards)
    if len(cards) > MAX_CARDS_SHOWN:
        cards = cards[:DEFAULT_CARDS_SHOWN]
    if len(cards) == 1:
        text = single_card_text_internal(client, cards[0], disable_emoji)
    else:
        text = ', '.join('{name} {legal} {price}'.format(name=card.name, legal=((emoji.legal_emoji(card)) if not disable_emoji else ''), price=((fetcher.card_price_string(card, True)) if card.get('mode', None) == '$' else '')) for card in cards)
    if len(cards) > MAX_CARDS_SHOWN:
        image_file = None
    else:
        image_file = image_fetcher.download_image(cards)
    if image_file is None:
        text += '\n\n'
        if len(cards) == 1:
            text += emoji.replace_emoji(cards[0].text, client)
        else:
            text += 'No image available.'
    text += additional_text
    if image_file is None:
        await channel.send(text)
    else:
        await send_image_with_retry(channel, image_file, text)

async def post_no_cards(channel: TextChannel, replying_to: Member) -> None:
    if replying_to is not None:
        text = '{author}: No matches.'.format(author=replying_to.mention)
    else:
        text = 'No matches.'
    message = await channel.send(text)
    await message.add_reaction('❎')

async def send_image_with_retry(channel: TextChannel, image_file: str, text: str = '') -> None:
    message = await channel.send(file=File(image_file), content=text)
    if message and message.attachments and message.attachments[0].size == 0:
        print('Message size is zero so resending')
        await message.delete()
        await channel.send(file=File(image_file), content=text)

def single_card_text_internal(client: Client, requested_card: Card, disable_emoji: bool) -> str:
    mana = emoji.replace_emoji(''.join(requested_card.mana_cost or []), client)
    legal = ' — ' + emoji.legal_emoji(requested_card, True)
    if disable_emoji:
        legal = ''
    if requested_card.get('mode', None) == '$':
        text = '{name} {legal} — {price}'.format(name=requested_card.name, price=fetcher.card_price_string(requested_card), legal=legal)
    else:
        text = '{name} {mana} — {type}{legal}'.format(name=requested_card.name, mana=mana, type=requested_card.type, legal=legal)
    if requested_card.bugs:
        for bug in requested_card.bugs:
            text += '\n:beetle:{rank} bug: {bug}'.format(bug=bug['description'], rank=bug['classification'])
            if bug['last_confirmed'] < (dtutil.now() - datetime.timedelta(days=60)):
                time_since_confirmed = (dtutil.now() - bug['last_confirmed']).total_seconds()
                text += ' (Last confirmed {time} ago.)'.format(time=dtutil.display_time(time_since_confirmed, 1))
    return text
