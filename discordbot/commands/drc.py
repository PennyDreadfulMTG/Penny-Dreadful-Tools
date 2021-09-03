from typing import Dict, List, Tuple, Optional

from discord import Embed
from discord.ext import commands

from discordbot.command import MAX_CARDS_SHOWN, DEFAULT_CARDS_SHOWN, MtgContext
from magic import oracle, fetcher
from shared import configuration, fetch_tools
from json import JSONDecodeError

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

@commands.command(aliases=['dreadrise', 'ds'])
async def drc(ctx: MtgContext, *, args: str) -> None:
    """Card search using Dreadrise."""
    count, error = await fetcher.dreadrise_count_cards(args)
    if error:
        await ctx.send(f'Search error: `{error}`')
        return

    cards_shown = DEFAULT_CARDS_SHOWN if count > MAX_CARDS_SHOWN else count
    cardnames = await fetcher.dreadrise_search_cards(args, cards_shown, 1)
    if len(cardnames) < cards_shown:
        cardnames += await fetcher.dreadrise_search_cards(args, cards_shown - len(cardnames), -1)

    cbn = oracle.cards_by_name()
    cards = [cbn[name] for name in cardnames if cbn.get(name) is not None]
    if count > DEFAULT_CARDS_SHOWN:
        cards = cards[:MAX_CARDS_SHOWN]
    await ctx.post_cards(cards, ctx.author, more_results_link(args, count))

@commands.command(aliases=['dd', 'deck'])
async def decks(ctx: MtgContext, *, args: str) -> None:
    """Deck search using Dreadrise."""
    q = fetch_tools.escape(args)
    url = f'{domain}/decks/find?q={q}+output:json_api&page_size={MAX_DECKS_SHOWN}'

    try:
        output = await fetch_tools.fetch_json_async(url)
    except (fetch_tools.FetchException, JSONDecodeError):
        print(f'Unable to parse json at {url}')
        return

    if output['error']:
        await ctx.send('Search error: `{err}`'.format(err=output['error']))
        return

    if output['length'] == 0:
        await ctx.post_nothing()
        return

    embed = Embed(title='Deck search', description='Winrate: {w}%'.format(w=output['winrate']))
    if output['length'] <= MAX_DECKS_SHOWN:
        arr = [format_deck(x) for x in output['data']]
    else:
        data = output['data'][:MAX_DECKS_SHOWN_WITH_CONTINUATION]
        arr = [format_deck(x) for x in data]
        arr.append({'name': 'Other results', 'value': '[{n} more results found]({domain}/minimize/{url})'.format(
            domain=link_domain,
            n=output['length'] - MAX_DECKS_SHOWN_WITH_CONTINUATION,
            url=output['compress'],
        )})

    embed.set_thumbnail(url='https://api.scryfall.com/cards/named?exact={card}&format=image&version=art_crop'.format(
        card=output['data'][0]['main_cards'][0].replace(' ', '%20')))
    for x in arr:
        embed.add_field(name=x['name'], value=x['value'], inline=False)
    await ctx.send(embed=embed)

@commands.command(aliases=['mu', 'mus'])
async def matchups(ctx: MtgContext, *, args: str) -> None:
    """Matchup calculation using Dreadrise. Accepts two queries separated by exclamation mark !."""
    q1, q2 = map(fetch_tools.escape, args.split('!'))
    url = f'{domain}/matches/find?q1={q1}&q2={q2}&api=1'
    try:
        output = await fetch_tools.fetch_json_async(url)
    except (fetch_tools.FetchException, JSONDecodeError):
        print(f'Unable to parse json at {url}')
        return

    if output['error']:
        await ctx.send('Search error: `{err}`'.format(err=output['error']))
        return

    if output['length'] == 0:
        await ctx.post_nothing()
        return

    ans = '{length} matches found. Winrate: {wr}%\n{domain}/minimize/{url}'.format(
        domain=link_domain, length=output['length'], wr=output['winrate'], url=output['compress'])
    await ctx.send(ans)

def more_results_link(args: str, total: int) -> str:
    return 'and {n} more.\n<{d}/cards/find?q={q}>'.format(
        n=total - DEFAULT_CARDS_SHOWN, q=fetch_tools.escape(args), d=link_domain) if total > MAX_CARDS_SHOWN else ''
