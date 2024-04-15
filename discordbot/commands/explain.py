import textwrap

import inflect
from interactions import AutocompleteContext
from interactions.client import Client
from interactions.ext.prefixed_commands import prefixed_command
from interactions.models import (TYPE_MESSAGEABLE_CHANNEL, Extension, OptionType, slash_command,
                                 slash_option)

from discordbot.command import MtgContext, MtgMessageContext, make_choice
from magic import card_price, fetcher, oracle, rotation, tournaments
from shared import configuration

num_tournaments = inflect.engine().number_to_words(str(len(tournaments.all_series_info())))
explanations: dict[str, tuple[str, dict[str, str]]] = {
    'archetype': (
        """
        Archetypes are manually reviewed by a human on an irregular basis.
        Prior to that a deck will have either its assigned archetype on Gatherling (tournament decks), nothing, or a best-guess based on the most similar reviewed deck (league decks).
        If you want to help out let us know.
        """,
        {},
    ),
    'bugs': (
        'We keep track of cards that are bugged on Magic Online. We allow the playing of cards with known bugs in Penny Dreadful under certain conditions. See the full rules on the website.',
        {
            'Known Bugs List': fetcher.decksite_url('/bugs/'),
            'Tournament Rules': fetcher.decksite_url('/tournaments/#bugs'),
            'Bugged Cards Database': 'https://github.com/PennyDreadfulMTG/modo-bugs/issues/',
        },

    ),
    'deckbuilding': (
        """
        The best way to build decks is to use a search engine that supports Penny Dreadful legality (`f:pd`) like Scryfall.
        You can find Penny Dreadful decklists from tournaments, leagues and elsewhere at pennydreadfulmagic.com.
        """,
        {
            'Scryfall': 'https://scryfall.com/',
            'Latest Decks': fetcher.decksite_url('/'),
            'Legal Cards List': 'http://pdmtgo.com/legal_cards.txt',
        },
    ),
    'decklists': (
        """
        You can find Penny Dreadful decklists from tournaments, leagues and elsewhere at pennydreadfulmagic.com
        """,
        {
            'Latest Decks': fetcher.decksite_url('/'),
        },
    ),
    'doorprize': (
        "The door prize is 1 tik credit with Cardhoarder, awarded to one randomly-selected player that completes the Swiss rounds but doesn't make top 8.",
        {},
    ),
    'gamehistory': (
        'You can find your Game History under the gear icon in the top right on MTGO. Latest match is at the bottom.',
        {},
    ),
    'language': (
        """
        To change the language you see the site in use the language switcher in the top-left hand corner (desktop only) or follow the link below for English.
        """,
        {
            'PDM in English': fetcher.decksite_url('/?locale=en'),
        },
    ),
    'league': (
        """
        Leagues last for roughly a month. You may enter any number of times but only one deck at a time.
        You play five matches per run. You can join the league at any time.
        To find a game sign up and then create a game in Constructed, Specialty, Freeform Tournament Practice with "Penny Dreadful League" as the comment.
        Top 8 finishers on each month's league leaderboard win credit with Cardhoarder.
        """,
        {
            'More Info': fetcher.decksite_url('/league/'),
            'Sign Up': fetcher.decksite_url('/signup/'),
            'Current League': fetcher.decksite_url('/league/current/'),
        },
    ),
    'netdecking': (
        """
        Netdecking is both allowed and encouraged. Most deck creators are happy when others play their decks.
        You can get a glimpse of the meta via the archetypes link below. Sort by win percent to find the best-performing decks.
        """,
        {
            'Archetypes': fetcher.decksite_url('/archetypes/'),
            'All Decklists': fetcher.decksite_url('/decks/'),
        },
    ),
    'nextround': (
        """
        The next round will begin when all matches are finished.
        You can check the reported and unreported results by looking at the pinned message in <#334220558159970304>
        """,
        {},
    ),
    'noshow': (
        """
        If your opponent does not join your game please @-message them on Discord and contact them on Magic Online.
        If you haven't heard from them by 10 minutes after the start of the round let the Tournament Organizer know.
        You will receive a 2-0 win and your opponent will be dropped from the competition.
        """,
        {},
    ),
    'onegame': (
        """
        If your opponent concedes or times out before the match completes, PDBot will not report automatically.
        If you feel enough of a match was played you may manually report 2-x where x is the number of games your opponent won.
        """,
        {
            'Report': fetcher.decksite_url('/report/'),
        },
    ),
    'playing': (
        """
        To get a match go to Constructed, Specialty, Freeform Tournament Practice on MTGO and create a match with "Penny Dreadful" in the comments.
        """,
        {},
    ),
    'prices': (
        f"""
        The price output contains current price.
        If the price is low enough it will show season-low and season-high also.
        If the card has been {card_price.MAX_PRICE_TEXT} or less at any point this season it will also include the amount of time (as a percentage) the card has spent at {card_price.MAX_PRICE_TEXT} or below this week, month and season.
        """,
        {},
    ),
    'prizes': (
        """
        Gatherling tournaments pay prizes to the Top 8 in Cardhoarder credit.
        This credit will appear when you trade with one of their bots on Magic Online.
        One player not making Top 8 but playing all the Swiss rounds will be randomly allocated the door prize.
        Prizes are credited once a week usually on the Friday or Saturday following the tournament but may sometimes take longer.
        """,
        {
            'More Info': fetcher.decksite_url('/tournaments/'),
        },
    ),
    'promos': (
        """
        """,
        {},

    ),
    'replay': (
        """
        You can play the same person a second time on your league run as long as they have started a new run. The same two runs cannot play each other twice.
        """,
        {},
    ),
    'reporting': (
        """
        """,
        {
        },
    ),
    'retire': (
        'To retire from a league run message PDBot on MTGO with `!retire`. If you have authenticated with Discord on pennydreadfulmagic.com you can say `!retire` on Discord or retire on the website.',
        {
            'Retire': fetcher.decksite_url('/retire/'),
        },
    ),
    'rotation': (
        f"""
        Legality is set a week after the release of a Standard-legal set on Magic Online.
        Prices are checked every hour for a week from the set release. Anything {card_price.MAX_PRICE_TEXT} or less for half or more of all checks is legal for the season.
        Any version of a card on the legal cards list is legal.
        """,
        {},
    ),
    'spectating': (
        """
        Spectating tournament and league matches is allowed and encouraged.
        Please do not write anything in chat except to call PDBot's `!record` command to find out the current score in games.
        """,
        {},
    ),
    'speculation': (
        """
        Please don't buy unconfirmed cards (marked ❓ during rotation), you may prevent them from becoming legal.
        """,
        {},
    ),
    'tournament': (
        f"""
        We have {num_tournaments} free-to-enter weekly tournaments that award trade credit prizes from Cardhoarder.
        They are hosted on gatherling.com along with a lot of other player-run Magic Online events.
        """,
        {
            'More Info': fetcher.decksite_url('/tournaments/'),
            'Sign Up': 'https://gatherling.com/',
        },
    ),
    'username': (
        """
        Please change your Discord username to include your MTGO username so we can know who you are.
        To change, right-click your username.
        This will not affect any other Discord channel.
        """,
        {},
    ),
    'wrongdeck': (
        """
        If a player realizes they have the wrong deck before the match begins they should take a screenshot of their opening hand as proof. Fix the deck and recreate the match. The player who had the wrong deck must give the choice of play or draw to their opponent.
        If a player realizes they have the wrong deck mid-game they receive a game loss for that game. The match should be recreated with the right deck and games conceded to get the match into the right state.
        """,
        {},
    ),
    'draws': (
        """
        Penny Dreadful tournaments follow official Magic Online tournament rules and do not allow intentional draws, unlike some other player-run events.
        """,
        {
            'More Tournament Info': fetcher.decksite_url('/tournaments/'),
        },
    ),
}
keys = sorted(explanations.keys())

explanations['drop'] = explanations['retire']
explanations['legality'] = explanations['rotation']
explanations['spectate'] = explanations['spectating']
explanations['tournaments'] = explanations['tournament']
explanations['watching'] = explanations['spectating']
explanations['spectate'] = explanations['spectating']

reporting_explanations: dict[str, tuple[str, dict[str, str]]] = {
    'tournament': (
        """
        For tournaments PDBot is information-only, *both* players must report near the top of Player CP (or follow the link at the top of any Gatherling page).
        """,
        {
            'Gatherling': 'https://gatherling.com/player.php',
        },
    ),
    'league': (
        """
        If PDBot reports your league match in <#220320082998460416> in Discord you don't need to do anything. If not, either player can report.
        """,
        {
            'League Report': fetcher.decksite_url('/report/'),
        },
    ),
}


class ExplainCog(Extension):
    @slash_command(
        name='explain',
        description='Answers for Frequently Asked Questions',
    )
    @slash_option(
        name='thing',
        description='Thing to be explained',
        opt_type=OptionType.STRING,
        required=True,
        autocomplete=True)
    async def explain(self, ctx: MtgContext, thing: str | None = None) -> None:
        """Answers for Frequently Asked Questions"""
        # strip trailing 's' to make 'leagues' match 'league' and simliar without affecting the output of `!explain` to be unnecessarily plural.
        if thing is None:
            thing = ''
        word = thing.lower().replace(' ', '').rstrip('s')
        if len(word) > 0:
            for k in explanations:
                if k.startswith(word):
                    word = k
        try:
            if word == 'reporting':
                if is_tournament_channel(ctx.channel):
                    explanation = reporting_explanations['tournament']
                else:
                    explanation = reporting_explanations['league']
            elif word == 'promos':
                explanation = promo_explanation()
            else:
                explanation = explanations[word]

            s = textwrap.dedent(explanation[0])
        except KeyError:
            usage = 'I can explain any of these things: {things}'.format(
                things=', '.join(sorted(keys)))
            await ctx.send(usage)
            return
        if word == 'rotation' and rotation.in_rotation():
            s += textwrap.dedent(explanations['speculation'][0]).strip()
        for k in sorted(explanation[1].keys()):
            s += f'{k}: <{explanation[1][k]}>\n'
        await ctx.send(s)

    @explain.autocomplete('thing')
    async def autocomplete_thing(self, ctx: AutocompleteContext) -> None:
        thing = ctx.input_text
        if not thing:
            await ctx.send(choices=list(make_choice(k) for k in keys[:20]))
            return
        choices = [k for k in keys if k.lower().startswith(thing.lower())]
        await ctx.send(choices=list(make_choice(c) for c in choices[:20]))

    async def reroute(self, ctx: MtgMessageContext) -> None:
        await self.explain.callback(ctx, ctx.content_parameters)

    m_explain = prefixed_command('explain')(reroute)

def is_tournament_channel(channel: TYPE_MESSAGEABLE_CHANNEL) -> bool:
    tournament_channel_id = configuration.get_int('tournament_channel_id')
    if not tournament_channel_id:
        return False
    return channel.id == tournament_channel_id

def promo_explanation() -> tuple[str, dict[str, str]]:
    explanation = 'Some cards have promos that are much cheaper than all other versions. The bot reports the cheapest version in stock.\nOther bot chains will have copies.'
    have_cheap_promos = [
        'Barbarian Ring',
        'Buried Alive',
        'Crystal Vein',
        'Lake of the Dead',
    ]
    legal_cheap_promos = [c for c in oracle.load_cards(have_cheap_promos) if c.pd_legal]
    if len(legal_cheap_promos) > 0:
        explanation += ' Affected cards include: ' + ', '.join(c.name for c in legal_cheap_promos)
    return (explanation, {})

def setup(bot: Client) -> None:
    ExplainCog(bot)
