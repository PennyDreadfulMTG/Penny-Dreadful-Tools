import collections
import glob
import os
import random
import re
import subprocess
import sys
import textwrap
import time
import traceback
from copy import copy
from typing import List

import inflect
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from discordbot import emoji
from find import search
from magic import (card, database, fetcher, image_fetcher, multiverse, oracle,
                   rotation, tournaments)
from shared import configuration, dtutil, repo
from shared.pd_exception import TooFewItemsException

DEFAULT_CARDS_SHOWN = 4
MAX_CARDS_SHOWN = 10
DISAMBIGUATION_EMOJIS = [':one:', ':two:', ':three:', ':four:', ':five:']
DISAMBIGUATION_EMOJIS_BY_NUMBER = {1 : '1⃣', 2 : '2⃣', 3 : '3⃣', 4 : '4⃣', 5 : '5⃣'}
DISAMBIGUATION_NUMBERS_BY_EMOJI = {'1⃣' : 1, '2⃣' : 2, '3⃣' : 3, '4⃣' : 4, '5⃣' : 5}

async def respond_to_card_names(message, bot):
    # Don't parse messages with Gatherer URLs because they use square brackets in the querystring.
    if 'gatherer.wizards.com' in message.content.lower():
        return
    queries = parse_queries(message.content)
    if len(queries) > 0:
        #cards = cards_from_queries(queries)
        results = cards_from_queries2(queries, bot)
        cards = []
        for r in results:
            if r.has_match() and not r.is_ambiguous():
                cards.extend(cards_from_names_with_mode([r.get_best_match()], r.mode))
            elif r.is_ambiguous():
                cards.extend(cards_from_names_with_mode(r.get_ambiguous_matches(), r.mode))
        await bot.post_cards(cards, message.channel, message.author)

    matches = re.findall(r'https?://(?:www.)?tappedout.net/mtg-decks/(?P<slug>[\w-]+)/?', message.content, flags=re.IGNORECASE)
    for match in matches:
        data = {"url": "https://tappedout.net/mtg-decks/{slug}".format(slug=match)}
        fetcher.internal.post(fetcher.decksite_url('/add/'), data)

async def handle_command(message, bot):
    parts = message.content.split(' ', 1)
    method = find_method(parts[0])

    if parts[0].lower() in configuration.get('otherbot_commands').split(','):
        return

    args = ""
    if len(parts) > 1:
        args = parts[1]


    if method is not None:
        try:
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
        except Exception as e: # pylint: disable=broad-except
            print('Caught exception processing command `{cmd}`'.format(cmd=message.content))
            tb = traceback.format_exc()
            print(tb)
            await bot.client.send_message(message.channel, '{author}: I know the command `{cmd}` but I could not do that.'.format(cmd=parts[0], author=message.author.mention))
            await getattr(Commands, 'bug')(Commands, bot, message.channel, 'Command failed with {c}: {cmd}\n\n```\n{tb}\n```'.format(c=e.__class__.__name__, cmd=message.content, tb=tb), message.author)

def find_method(name):
    cmd = name.lstrip('!').lower()
    if len(cmd) == 0:
        return None
    method = [m for m in dir(Commands) if m == cmd or m == '_' + cmd]
    if len(method) == 0:
        method = [m for m in dir(Commands) if m.startswith(cmd) or m.startswith('_{cmd}'.format(cmd=cmd))]
    if len(method) > 0:
        return getattr(Commands, method[0])
    return None

def build_help(readme=False, cmd=None):
    def print_group(group):
        msg = ''
        for methodname in dir(Commands):
            if methodname.startswith("__"):
                continue
            method = getattr(Commands, methodname)
            if getattr(method, "group", None) != group:
                continue
            msg += '\n' + print_cmd(method, readme)
        return msg

    def print_cmd(method, verbose):
        if method.__doc__:
            if not method.__doc__.startswith('`'):
                return '`!{0}` {1}'.format(method.__name__, method.__doc__)
            return '{0}'.format(method.__doc__)
        elif verbose:
            return '`!{0}` No Help Available'.format(method.__name__)
        return "`!{0}`".format(method.__name__)

    if cmd:
        method = find_method(cmd)
        if method:
            return print_cmd(method, True)
        return "`{cmd}` is not a valid command.".format(cmd=cmd)

    msg = print_group('Commands')
    if readme:
        msg += "\n# Developer Commands"
        msg += print_group('Developer')
    return msg

def cmd_header(group):
    def decorator(func):
        setattr(func, "group", group)
        return func
    return decorator



# pylint: disable=too-many-public-methods
class Commands:
    """To define a new command, simply add a new method to this class.
    If you want !help to show the message, add a docstring to the method.
    Method parameters should be in the format:
    `async def commandname(self, bot, channel, args, author)`
    Where any argument after self is optional. (Although at least channel is usually needed)
    """

    @cmd_header('Commands')
    async def help(self, bot, channel, args):
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
            await bot.client.send_message(channel, msg[0:1999] + '…')
        else:
            await bot.client.send_message(channel, msg)

    @cmd_header('Commands')
    async def random(self, bot, channel, args):
        """`!random` Request a random PD legal card.
`!random X` Request X random PD legal cards."""
        number = 1
        if len(args) > 0:
            try:
                number = int(args.strip())
            except ValueError:
                pass
        cards = [oracle.cards_by_name()[name] for name in random.sample(oracle.legal_cards(), number)]
        await bot.post_cards(cards, channel)

    @cmd_header('Developer')
    async def update(self, bot, channel):
        """Forces an update to legal cards and bugs."""
        oracle.legal_cards(force=True)
        multiverse.update_bugged_cards()
        await bot.client.send_message(channel, 'Reloaded legal cards and bugs.')

    @cmd_header('Developer')
    async def restartbot(self, bot, channel):
        """Restarts the bot."""
        await bot.client.send_message(channel, 'Rebooting!')
        sys.exit()

    @cmd_header('Commands')
    async def search(self, bot, channel, args, author):
        """`!search {query}` Search for cards, using a scryfall-style query."""
        try:
            cards = complex_search(args)
        except search.InvalidSearchException as e:
            return await bot.client.send_message(channel, '{author}: {e}'.format(author=author.mention, e=e))
        await bot.post_cards(cards, channel, author, more_results_link(args, len(cards)))

    @cmd_header('Commands')
    async def scryfall(self, bot, channel, args, author):
        """`!scryfall {query}` Search for cards using Scryfall."""
        await bot.client.send_typing(channel)
        how_many, cardnames = fetcher.search_scryfall(args)
        cbn = oracle.cards_by_name()
        cards = [cbn.get(name) for name in cardnames if cbn.get(name) is not None]
        await bot.post_cards(cards, channel, author, more_results_link(args, how_many))

    @cmd_header('Commands')
    async def status(self, bot, channel):
        """`!status` Gives the status of Magic Online: UP or DOWN."""
        status = fetcher.mtgo_status()
        await bot.client.send_message(channel, 'MTGO is {status}'.format(status=status))

    @cmd_header('Developer')
    async def echo(self, bot, channel, args):
        """Repeat after me…"""
        s = emoji.replace_emoji(args, bot.client)
        await bot.client.send_message(channel, s)

    @cmd_header('Commands')
    async def barbs(self, bot, channel):
        """`!barbs` Gives Volvary's helpful advice for when to sideboard in Aura Barbs."""
        msg = "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."
        await bot.client.send_message(channel, msg)

    @cmd_header('Commands')
    async def quality(self, bot, channel):
        """`!quality` A helpful reminder about everyone's favorite way to play digital Magic"""
        msg = "**Magic Online** is a Quality™ Program."
        await bot.client.send_message(channel, msg)

    @cmd_header('Commands')
    async def rhinos(self, bot, channel):
        """`!rhinos` Anything can be a rhino if you try hard enough"""
        rhinos = []
        rhino_name = "Siege Rhino"
        if random.random() < 0.05:
            rhino_name = "Abundant Maw"
        rhinos.extend([oracle.cards_by_name()[rhino_name]])
        def find_rhino(query):
            cards = complex_search('f:pd {0}'.format(query))
            if len(cards) == 0:
                cards = complex_search(query)
            return random.choice(cards)
        rhinos.append(find_rhino('o:"copy of target creature"'))
        rhinos.append(find_rhino('o:"return target creature card from your graveyard to the battlefield"'))
        rhinos.append(find_rhino('o:"search your library for a creature"'))
        msg = "\nSo of course we have {rhino}.".format(rhino=rhinos[0].name)
        msg += " And we have {copy}. It can become a rhino, so that's a rhino.".format(copy=rhinos[1].name)
        msg += " Then there's {reanimate}. It can get back one of our rhinos, so that's a rhino.".format(reanimate=rhinos[2].name)
        msg += " And then we have {search}. It's a bit of a stretch, but that's a rhino too.".format(search=rhinos[3].name)
        await bot.post_cards(rhinos, channel, additional_text=msg)

    @cmd_header('Commands')
    async def rotation(self, bot, channel):
        """`!rotation` Give the date of the next Penny Dreadful rotation."""
        next_rotation = rotation.next_rotation()
        next_supplemental = rotation.next_supplemental()
        now = dtutil.now()
        sdiff = next_supplemental - now
        diff = next_rotation - now
        if sdiff < diff:
            msg = "The supplemental rotation is in {sdiff} (The next full rotation is in {diff})".format(diff=dtutil.display_time(diff.total_seconds()), sdiff=dtutil.display_time(sdiff.total_seconds()))
        else:
            msg = "The next rotation is in {diff}".format(diff=dtutil.display_time(diff.total_seconds()))
        await bot.client.send_message(channel, msg)

    @cmd_header('Commands')
    async def rulings(self, bot, channel, args, author):
        """`!rulings {name}` Display rulings for a card."""
        await bot.client.send_typing(channel)
        await single_card_text(bot, channel, args, author, card_rulings, "rulings")

    @cmd_header('Commands')
    async def _oracle(self, bot, channel, args, author):
        """`!oracle {name}` Give the Oracle text of the named card."""
        await single_card_text(bot, channel, args, author, oracle_text, "oracle")

    @cmd_header('Commands')
    async def price(self, bot, channel, args, author):
        """`!price {name}` Get price information about the named card."""
        await single_card_text(bot, channel, args, author, fetcher.card_price_string, "price")

    @cmd_header('Commands')
    async def legal(self, bot, channel, args, author):
        """Announce whether the specified card is legal or not."""
        await single_card_text(bot, channel, args, author, lambda c: '', "legal")

    @cmd_header('Commands')
    async def modofail(self, bot, channel, args, author):
        """Ding!"""
        if args.lower() == "reset":
            self.modofail.count = 0
        if hasattr(author, 'voice') and author.voice is not None and author.voice.voice_channel is not None:
            voice_channel = author.voice.voice_channel
            voice = channel.server.voice_client
            if voice is None:
                voice = await bot.client.join_voice_channel(voice_channel)
            elif voice.channel != voice_channel:
                voice.move_to(voice_channel)
            ding = voice.create_ffmpeg_player("ding.ogg")
            ding.start()
        if time.time() > self.modofail.last_fail + 60 * 60:
            self.modofail.count = 0
        self.modofail.count += 1
        self.modofail.last_fail = time.time()
        await bot.client.send_message(channel, ':bellhop: **MODO fail** {0}'.format(self.modofail.count))
    modofail.count = 0
    modofail.last_fail = time.time()

    @cmd_header('Commands')
    async def resources(self, bot, channel, args):
        """`!resources {args}` Link to useful pages related to `args`. Examples: 'tournaments', 'card Hymn to Tourach', 'deck check', 'league'."""
        results = {}
        if len(args) > 0:
            results.update(resources_resources(args))
            results.update(site_resources(args))
        s = ''
        if len(results) == 0:
            s = 'PD resources: <{url}>'.format(url=fetcher.decksite_url('/resources/'))
        else:
            for url, text in results.items():
                s += '{text}: <{url}>\n'.format(text=text, url=url)
        await bot.client.send_message(channel, s)

    @cmd_header('Developer')
    async def clearimagecache(self, bot, channel):
        """Deletes all the cached images.  Use sparingly"""
        image_dir = configuration.get('image_dir')
        if not image_dir:
            return await bot.client.send_message(channel, 'Cowardly refusing to delete from unknown image_dir.')
        files = glob.glob('{dir}/*.jpg'.format(dir=image_dir))
        for file in files:
            os.remove(file)
        await bot.client.send_message(channel, '{n} cleared.'.format(n=len(files)))

    @cmd_header('Developer')
    async def notpenny(self, bot, channel, args):
        """Don't show PD Legality in this channel"""
        existing = configuration.get('not_pd')
        if args and args[0] == "server":
            cid = channel.server.id
        else:
            cid = channel.id
        if str(cid) not in existing.split(','):
            configuration.write('not_pd', "{0},{1}".format(existing, cid))
        await bot.client.send_message(channel, 'Disable PD marks')

    @cmd_header('Commands')
    async def bug(self, bot, channel, args, author):
        """Report a bug/task for the Penny Dreadful Tools team. For MTGO bugs see `!modobug`."""
        await bot.client.send_typing(channel)
        issue = repo.create_issue(args, author)
        if issue is None:
            await bot.client.send_message(channel, "Report issues at <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/new>")
        else:
            await bot.client.send_message(channel, "Issue has been reported at <{url}>".format(url=issue.html_url))

    @cmd_header('Commands')
    async def modobug(self, bot, channel, args, author):
        """Report a Magic Online bug."""
        await bot.client.send_typing(channel)
        issue = repo.create_issue(args, author, 'Discord', 'PennyDreadfulMTG/modo-bugs')
        if issue is None:
            await bot.client.send_message(channel, 'Report Magic Online issues at <https://github.com/PennyDreadfulMTG/modo-bugs/issues/new>')
        else:
            await bot.client.send_message(channel, 'Issue has been reported at <{url}>. Please add square brackets and screenshot as explained here: <https://github.com/PennyDreadfulMTG/modo-bugs/blob/master/README.md>'.format(url=issue.html_url))

    @cmd_header('Commands')
    async def gbug(self, bot, channel, args, author):
        """Report a Gatherling bug."""
        await bot.client.send_typing(channel)
        issue = repo.create_issue(args, author, 'Discord', 'PennyDreadfulMTG/gatherling')
        if issue is None:
            await bot.client.send_message(channel, 'Report Gatherling issues at <https://github.com/PennyDreadfulMTG/gatherling/issues/new>')
        else:
            await bot.client.send_message(channel, 'Issue has been reported at <{url}>.'.format(url=issue.html_url))


    @cmd_header('Commands')
    async def invite(self, bot, channel):
        """Invite me to your server."""
        await bot.client.send_message(channel, "Invite me to your discord server by clicking this link: <https://discordapp.com/oauth2/authorize?client_id=224755717767299072&scope=bot&permissions=268757056>")

    @cmd_header('Commands')
    async def spoiler(self, bot, channel, args, author):
        """`!spoiler {cardname}`: Request a card from an upcoming set."""
        if len(args) == 0:
            return await bot.client.send_message(channel, '{author}: Please specify a card name.'.format(author=author.mention))
        sfcard = fetcher.internal.fetch_json('https://api.scryfall.com/cards/named?fuzzy={name}'.format(name=args))
        if sfcard['object'] == 'error':
            return await bot.client.send_message(channel, '{author}: {details}'.format(author=author.mention, details=sfcard['details']))
        imagename = '{set}_{number}'.format(set=sfcard['set'], number=sfcard['collector_number'])
        imagepath = '{image_dir}/{imagename}.jpg'.format(image_dir=configuration.get('image_dir'), imagename=imagename)
        if sfcard.get('card_faces'):
            c = sfcard['card_faces'][0]
        else:
            c = sfcard
        fetcher.internal.store(c['image_uris']['normal'], imagepath)
        text = emoji.replace_emoji('{name} {mana}'.format(name=sfcard['name'], mana=c['mana_cost']), bot.client)
        await bot.client.send_file(channel, imagepath, content=text)
        oracle.scryfall_import(sfcard['name'])

    @cmd_header('Commands')
    async def time(self, bot, channel, args, author):
        """`!time {location}` Show the current time in the specified location."""
        try:
            t = fetcher.time(args.strip())
        except TooFewItemsException:
            return await bot.client.send_message(channel, '{author}: Location not found.'.format(author=author.mention))
        await bot.client.send_message(channel, '{args}: {time}'.format(args=args, time=t))

    @cmd_header('Commands')
    async def pdm(self, bot, channel, args):
        """Alias for `!resources`."""
        # Because of the weird way we call and use methods on Commands we need …
        # pylint: disable=too-many-function-args
        await self.resources(self, bot, channel, args)

    @cmd_header('Commands')
    async def google(self, bot, channel, args, author):
        """`!google {args}` Search google for `args`."""
        await bot.client.send_typing(channel)

        api_key = configuration.get('cse_api_key')
        cse_id = configuration.get('cse_engine_id')
        if api_key is None or cse_id is None:
            return await bot.client.send_message(channel, 'The google command has not been configured.')

        if len(args.strip()) == 0:
            return await bot.client.send_message(channel, '{author}: No search term provided. Please type !google followed by what you would like to search'.format(author=author.mention))

        try:
            service = build("customsearch", "v1", developerKey=api_key)
            res = service.cse().list(q=args, cx=cse_id, num=1).execute() # pylint: disable=no-member
            if 'items' in res:
                r = res['items'][0]
                s = '{title} <{url}> {abstract}'.format(title=r['title'], url=r['link'], abstract=r['snippet'])
            else:
                s = '{author}: Nothing found on Google.'.format(author=author.mention)
        except HttpError as e:
            if e.resp['status'] == "403":
                s = 'We have reached the allowed limits of Google API'
            else:
                raise e

        await bot.client.send_message(channel, s)

    @cmd_header('Commands')
    async def tournament(self, bot, channel):
        """`!tournament` Get information about the next tournament."""
        t = tournaments.next_tournament_info()
        prev = tournaments.previous_tournament_info()
        if prev['near']:
            started = "it started "
        else:
            started = ""
        prev_message = "The last tournament was {name}, {started}{time} ago".format(name=prev['next_tournament_name'], started=started, time=prev['next_tournament_time'])
        next_time = 'in ' + t['next_tournament_time'] if t['next_tournament_time'] != dtutil.display_time(0, 0) else t['next_tournament_time']
        await bot.client.send_message(channel, 'The next tournament is {name} {next_time}.\nSign up on <http://gatherling.com/>\nMore information: {url}\n{prev_message}'.format(name=t['next_tournament_name'], next_time=next_time, prev_message=prev_message, url=fetcher.decksite_url('/tournaments/')))

    @cmd_header('Commands')
    async def art(self, bot, channel, args, author):
        """`!art {name}` Display the art (only) of the most recent printing of the named card."""
        await bot.client.send_typing(channel)
        c = await single_card_or_send_error(bot, channel, args, author, "art")
        if c is not None:
            image_file = image_fetcher.download_scryfall_image([c], image_fetcher.determine_filepath([c]) + '.art_crop.jpg', version='art_crop')
            await bot.send_image_with_retry(channel, image_file)

    @cmd_header('Commands')
    async def explain(self, bot, channel, args):
        """`!explain`. Get a list of things the bot knows how to explain.
`!explain {thing}`. Print commonly needed explanation for 'thing'."""
        num_tournaments = inflect.engine().number_to_words(len(tournaments.all_series_info()))
        explanations = {
            'bugs': [
                'We keep track of cards that are bugged on Magic Online. We allow the playing of cards with known bugs in Penny Dreadful under certain conditions. See the full rules on the website.',
                {
                    'Known Bugs List': fetcher.decksite_url('/bugs/'),
                    'Tournament Rules': fetcher.decksite_url('/tournaments/#bugs'),
                    'Bugged Cards Database': 'https://github.com/PennyDreadfulMTG/modo-bugs/issues/'
                }

            ],
            'deckbuilding': [
                """
                The best way to build decks is to use a search engine that supports Penny Dreadful legality (`f:pd`) like Scryfall.
                You can find Penny Dreadful decklists from tournaments, leagues and elsewhere at pennydreadfulmagic.com.
                """,
                {
                    'Scryfall': 'https://scryfall.com/',
                    'Latest Decks': fetcher.decksite_url('/'),
                    'Legal Cards List': 'http://pdmtgo.com/legal_cards.txt'
                }
            ],
            'decklists': [
                """
                You can find Penny Dreadful decklists from tournaments, leagues and elsewhere at pennydreadfulmagic.com
                """,
                {
                    'Latest Decks': fetcher.decksite_url('/')
                }
            ],
            'league': [
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
            ],
            'legality': [
                """
                Legality is determined at the release of a Standard-legal set on Magic Online.
                Prices are checked every hour for a week. Anything 1c or less for half or more of all checks is legal for the season.
                Cards from the just-released set are added (nothing removed) a couple of weeks later via a supplemental rotation after prices have settled a little.
                Any version of a card on the legal cards list is legal.
                """,
                {
                    'Deck Checker': 'http://pdmtgo.com/deck_check.html',
                    'Legal Cards List': 'http://pdmtgo.com/legal_cards.txt'
                }
            ],
            'noshow': [
                """
                If your opponent does not join your game please @-message them on Discord and contact them on Magic Online.
                If you haven't heard from them by 10 minutes after the start of the round let the Tournament Organizer know.
                You will receive a 2-0 win and your opponent will be dropped from the competition.
                """
            ],
            'playing': [
                """
                To get a match go to Constructed Open Play, Just for Fun on MTGO and create a Freeform game with "Penny Dreadful" in the comments.
                """,
                {}
            ],
            'prices': [
                """
                The price output contains current price.
                If the price is low enough it will show season-low and season-high also.
                If the card has been 1c at any point this season it will also include the amount of time (as a percentage) the card has spent at 1c or below this week, month and season.
                """,
                {}
            ],
            'prizes': [
                """
                Gatherling tournaments pay prizes to the Top 8 in Cardhoarder credit.
                One player not making Top 8 but playing all the Swiss rounds will be randomly allocated the door prize.
                Prizes are credited once a week usually on the Friday or Saturday following the tournament but may sometimes take longer.
                """,
                {
                    'More Info': fetcher.decksite_url('/tournaments/')
                }
            ],
            'report': [
                """
                For gatherling.com tournaments PDBot is information-only, *both* players must report near the top of Player CP.
                If PDBot reports your league match in Discord you don't need to do anything (only league matches, tournament matches must still be reported). If not, either player can report.
                """,
                {
                    'Gatherling': 'https://gatherling.com/player.php',
                    'League Report': fetcher.decksite_url('/report/')
                }
            ],
            'retire': [
                'To retire from a league run message PDBot on MTGO with !retire. Alternatively retire via pennydreadfulmagic.com (requires Discord authentication)',
                {
                    'Retire': fetcher.decksite_url('/retire/')
                }
            ],
            'tournament': [
                """
                We have {num_tournaments} free-to-enter weekly tournaments with prizes from Cardhoarder.
                They are hosted on gatherling.com along with a lot of other player-run Magic Online events.
                """.format(num_tournaments=num_tournaments),
                {
                    'More Info': fetcher.decksite_url('/tournaments/'),
                    'Sign Up': 'https://gatherling.com/',
                }
            ],
            'username': [
                """
                Please change your Discord username to include your MTGO username so we can know who you are.
                To change, right-click your username.
                This will not affect any other Discord channel.
                """
            ]
        }
        keys = sorted(explanations.keys())
        explanations['drop'] = explanations['retire']
        explanations['rotation'] = explanations['legality']
        explanations['tournaments'] = explanations['tournament']
        word = args.strip()
        if len(word) > 0:
            for k in explanations:
                if k.startswith(word):
                    word = k
        try:
            s = '{text}\n'.format(text=textwrap.dedent(explanations[word][0]))
        except KeyError:
            usage = 'I can explain any of these things: {things}'.format(things=', '.join(sorted(keys)))
            return await bot.client.send_message(channel, usage)
        if len(explanations[word]) >= 2:
            for k in sorted(explanations[word][1].keys()):
                s += '{k}: <{v}>\n'.format(k=k, v=explanations[word][1][k])
        await bot.client.send_message(channel, s)

    @cmd_header('Developer')
    async def version(self, bot, channel):
        """Display the current version numbers"""
        await bot.client.send_typing(channel)
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
        mtgjson = database.mtgjson_version()
        return await bot.client.send_message(channel, "I am currently running mtgbot version `{commit}`, and mtgjson version `{mtgjson}`".format(commit=commit, mtgjson=mtgjson))

# Given a list of cards return one (aribtrarily) for each unique name in the list.
def uniqify_cards(cards):
    # Remove multiple printings of the same card from the result set.
    results = collections.OrderedDict()
    for c in cards:
        results[card.canonicalize(c.name)] = c
    return list(results.values())

def parse_queries(content: str) -> List[str]:
    queries = re.findall(r'\[?\[([^\]]*)\]\]?', content)
    return [card.canonicalize(query) for query in queries if len(query) > 2]

def cards_from_queries(queries):
    all_cards = []
    for query in queries:
        cards = oracle.cards_from_query(query)
        if len(cards) > 0:
            all_cards.extend(cards)
    return all_cards



def cards_from_names_with_mode(cards, mode):
    oracle_cards = oracle.cards_by_name()
    return [copy_with_mode(oracle_cards[c], mode) for c in cards if c is not None]

def copy_with_mode(oracle_card, mode):
    c = copy(oracle_card)
    c['mode'] = mode
    return c

def parse_mode(query):
    mode = 0
    if query.startswith('$'):
        mode = '$'
        query = query[1:]
    return [mode, query]

def cards_from_queries2(queries, bot):
    all_results = []
    for query in queries:
        mode, query = parse_mode(query)
        result = bot.searcher.search(query)
        result.mode = mode
        all_results.append(result)
    return all_results

def complex_search(query):
    if query == '':
        return []
    return search.search(query)

def roughly_matches(s1, s2):
    return simplify_string(s1).find(simplify_string(s2)) >= 0

def simplify_string(s):
    s = ''.join(s.split())
    return re.sub(r'[\W_]+', '', s).lower()

def disambiguation(cards):
    if len(cards) > 5:
        return ",".join(cards)
    return " ".join([" ".join(x) for x in zip(DISAMBIGUATION_EMOJIS, cards)])

async def disambiguation_reactions(bot, message, cards):
    for i in range(1, len(cards)+1):
        await bot.client.add_reaction(message, DISAMBIGUATION_EMOJIS_BY_NUMBER[i])

async def single_card_or_send_error(bot, channel, args, author, command):
    result = cards_from_queries2([args], bot)[0]
    if result.has_match() and not result.is_ambiguous():
        return cards_from_names_with_mode([result.get_best_match()], result.mode)[0]

    if result.is_ambiguous():
        message = await bot.client.send_message(channel, '{author}: Ambiguous name for {c}. Suggestions: {s}'.format(author=author.mention, c=command, s=disambiguation(result.get_ambiguous_matches()[0:5])))
        await disambiguation_reactions(bot, message, result.get_ambiguous_matches()[0:5])
    else:
        await bot.client.send_message(channel, '{author}: No matches.'.format(author=author.mention))

# pylint: disable=too-many-arguments
async def single_card_text(bot, channel, args, author, f, command):
    c = await single_card_or_send_error(bot, channel, args, author, command)
    if c is not None:
        legal_emoji = emoji.legal_emoji(c)
        text = emoji.replace_emoji(f(c), bot.client)
        message = '**{name}** {legal_emoji} {text}'.format(name=c.name, legal_emoji=legal_emoji, text=text)
        await bot.client.send_message(channel, message)

def oracle_text(c):
    return c.text

def card_rulings(c):
    rulings = fetcher.rulings(c.name)
    rulings = [r['comment'] for r in rulings]
    if len(rulings) > 3:
        n = len(rulings) - 2
        rulings = rulings[:2]
        rulings.append("And {n} others.  See <https://scryfall.com/search?q=%21%22{cardname}%22>".format(n=n, cardname=fetcher.internal.escape(c.name)))
    return "\n".join(rulings) or "No rulings available."

def site_resources(args):
    results = {}
    if ' ' in args.strip():
        area, detail = args.strip().split(' ', 1)
    else:
        area, detail = args.strip(), ''
    if area == 'archetype':
        area = 'archetypes'
    if area == 'card':
        area = 'cards'
    if area == 'person':
        area = 'people'
    sitemap = fetcher.sitemap()
    matches = [endpoint for endpoint in sitemap if endpoint.startswith('/{area}/'.format(area=area))]
    if len(matches) > 0:
        detail = '{detail}/'.format(detail=fetcher.internal.escape(detail)) if detail else ''
        url = fetcher.decksite_url('/{area}/{detail}'.format(area=fetcher.internal.escape(area), detail=detail))
        results[url] = args
    return results

def resources_resources(args):
    results = {}
    words = args.split()
    resources = fetcher.resources()
    for title, items in resources.items():
        for text, url in items.items():
            asked_for_this_section_only = len(words) == 1 and roughly_matches(title, words[0])
            asked_for_this_section_and_item = len(words) == 2 and roughly_matches(title, words[0]) and roughly_matches(text, words[1])
            asked_for_this_item_only = len(words) == 1 and roughly_matches(text, words[0])
            the_whole_thing_sounds_right = roughly_matches(text, ' '.join(words))
            if asked_for_this_section_only or asked_for_this_section_and_item or asked_for_this_item_only or the_whole_thing_sounds_right:
                results[url] = text
    return results

def more_results_link(args, total):
    return 'and {n} more.\n<https://scryfall.com/search/?q={q}>'.format(n=total - 4, q=fetcher.internal.escape(args)) if total > MAX_CARDS_SHOWN else ''
