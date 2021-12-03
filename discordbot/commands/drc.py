from typing import Dict

from dis_snek.models.application_commands import OptionTypes, slash_command, slash_option
from dis_snek.models.discord_objects.embed import Embed

from discordbot.command import DEFAULT_CARDS_SHOWN, MAX_CARDS_SHOWN, MtgContext
from magic import fetcher, oracle
from shared import configuration, fetch_tools

domain = configuration.get_str('dreadrise_url')
link_domain = configuration.get_str('dreadrise_public_url')
MAX_DECKS_SHOWN = 5
MAX_DECKS_SHOWN_WITH_CONTINUATION = 3

def format_deck(x: Dict) -> Dict:
    """Formats a deck object. Returns a dictionary with name and value."""
    return {
        'name': '{name} [{src} {wins}-{losses}]'.format(
            name=x['name'], wins=x['record']['wins'], losses=x['record']['losses'], src=x['source']),
        'value': '[A {arch} deck by {author} ({format})]({domain}/decks/single/{id})'.format(
            arch=x['archetype'], author=x['author'], format=x['printed_format'], id=x['id'], domain=link_domain),
    }

@slash_command('dreadrise',
        description='Dreadrise',
        sub_cmd_name='search',
        sub_cmd_description='Card Search using Dreadrise'
    )
@slash_option('query', 'search query', OptionTypes.STRING)
async def drc(ctx: MtgContext, query: str) -> None:
    """Card search using Dreadrise."""
    count, error = await fetcher.dreadrise_count_cards(query)
    if error:
        await ctx.send(f'Search error: `{error}`')
        return

    cards_shown = DEFAULT_CARDS_SHOWN if count > MAX_CARDS_SHOWN else count
    cardnames = await fetcher.dreadrise_search_cards(query, cards_shown, 1)
    if len(cardnames) < cards_shown:
        cardnames += await fetcher.dreadrise_search_cards(query, cards_shown - len(cardnames), -1)

    cbn = oracle.cards_by_name()
    cards = [cbn[name] for name in cardnames if cbn.get(name) is not None]
    if count > DEFAULT_CARDS_SHOWN:
        cards = cards[:MAX_CARDS_SHOWN]
    await ctx.post_cards(cards, ctx.author, more_results_link(query, count))

@drc.subcommand('deck')
@slash_option('query', 'search query', OptionTypes.STRING)
async def decks(ctx: MtgContext, query: str) -> None:
    """Deck search using Dreadrise."""

    count, output, error = await fetcher.dreadrise_search_decks(query, MAX_DECKS_SHOWN)
    if error:
        await ctx.send(f'Search error: `{error}`')
        return
    if count == 0:
        await ctx.post_nothing()
        return

    embed = Embed(title='Deck search', description='Winrate: {w}%'.format(w=output['winrate']))
    if count <= MAX_DECKS_SHOWN:
        arr = [format_deck(x) for x in output['data']]
    else:
        data = output['data'][:MAX_DECKS_SHOWN_WITH_CONTINUATION]
        arr = [format_deck(x) for x in data]
        arr.append({'name': 'Other results', 'value': '[{n} more results found]({domain}/minimize/{url})'.format(
            domain=link_domain,
            n=count - MAX_DECKS_SHOWN_WITH_CONTINUATION,
            url=output['compress'],
        )})

    embed.set_thumbnail(url='https://api.scryfall.com/cards/named?exact={card}&format=image&version=art_crop'.format(
        card=output['data'][0]['main_cards'][0].replace(' ', '%20')))
    for x in arr:
        embed.add_field(name=x['name'], value=x['value'], inline=False)
    await ctx.send(embed=embed)

@drc.subcommand('matchups')
async def matchups(ctx: MtgContext, *, args: str) -> None:
    """Matchup calculation using Dreadrise. Accepts two queries separated by exclamation mark !."""
    q_list = args.split('!')
    q1 = q_list[0]
    q2 = q_list[1] if len(q_list) >= 2 else ''
    count, output, error = await fetcher.dreadrise_search_matchups(q1, q2)
    if error:
        await ctx.send(f'Search error: `{error}`')
        return
    if count == 0:
        await ctx.post_nothing()
        return

    ans = '{length} matches found. Winrate: {wr}%\n{domain}/minimize/{url}'.format(
        domain=link_domain, length=count, wr=output['winrate'], url=output['compress'])
    await ctx.send(ans)

def more_results_link(args: str, total: int) -> str:
    return 'and {n} more.\n<{d}/cards/find?q={q}>'.format(
        n=total - DEFAULT_CARDS_SHOWN, q=fetch_tools.escape(args), d=link_domain) if total > MAX_CARDS_SHOWN else ''
