from discord.ext import commands
from discord import Embed

from discordbot.command import MAX_CARDS_SHOWN, MtgContext
from magic import fetcher, oracle
from shared import fetch_tools, configuration
from typing import List, Tuple, Dict

domain = configuration.get_str('dreadrise_url')
link_domain = configuration.get_str('dreadrise_public_url')
MAX_DECKS_SHOWN = 5
MAX_DECKS_SHOWN_WITH_CONTINUATION = 3

def format_deck(x: Dict) -> Dict:
    """Formats a deck object. Returns a dictionary with name and value."""
    return {
        'name': '{name} [{src} {wins}-{losses}]'.format(name=x['name'],
            wins=x['record']['wins'], losses=x['record']['losses'], src=x['source']),
        'value': '[A {arch} deck by {author} ({format})]({domain}/decks/single/{id})'.format(
            arch=x['archetype'], author=x['author'], format=x['printed_format'], id=x['id'], domain=link_domain),
    }

@commands.command(aliases=['dreadrise', 'ds'])
async def drc(ctx: MtgContext, *, args: str) -> None:
    """Card search using Dreadrise."""
    how_many, cardnames = search_dreadrise(args)
    cbn = oracle.cards_by_name()
    cards = [cbn[name] for name in cardnames if cbn.get(name) is not None]
    await ctx.post_cards(cards, ctx.author, more_results_link(args, how_many))

@commands.command(aliases=['dd', 'deck'])
async def decks(ctx: MtgContext, *, args: str) -> None:
    """Deck search using Dreadrise."""
    q = fetch_tools.escape(args)
    url = f'{domain}/decks/find?q={q}+output:json_api&page_size={MAX_DECKS_SHOWN}'

    try:
        output = fetch_tools.fetch_json(url)
    except fetch_tools.FetchException:
        print(f'Unable to parse json at {url}')
        return

    if output['length'] == 0:
        await ctx.post_no_matches()
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
    q1, q2 = map(fetch_tools.escape, args.split("!"))
    url = f'{domain}/matches/find?q1={q1}&q2={q2}&api=1'
    try:
        output = fetch_tools.fetch_json(url)
    except fetch_tools.FetchException:
        print(f'Unable to parse json at {url}')
        return

    if output['length'] == 0:
        await ctx.post_no_matches()
        return

    ans = '{length} matches found. Winrate: {wr}%\n{domain}/minimize/{url}'.format(
            domain=link_domain, length=output['length'], wr=output['winrate'], url=output['compress'])
    await ctx.send(ans)

def search_dreadrise(query: str) -> Tuple[int, List[str]]:
    """Returns a tuple. First member is an integer indicating how many cards match the query total,
       second member is a list of card names up to the maximum that could be fetched in a timely fashion."""
    if not query:
        return 0, []

    query = fetch_tools.escape(query)
    url1 = f'{domain}/cards/find?q={query}+output:resultcount'
    try:
        count = int(fetch_tools.fetch(url1))
    except ValueError:
        return 0, []

    # if we are here, the query is valid, so no need to check for ValueErrors
    url2 = f'{domain}/cards/find?q=f:pd+({query})+output:pagetext&page_size={MAX_CARDS_SHOWN}'
    pd_legals = str(fetch_tools.fetch(url2)).split('\n')
    if len(pd_legals) == MAX_CARDS_SHOWN:
        return count, pd_legals

    url3 = f'{domain}/cards/find?q=f:pd+({query})+output:pagetext&page_size={MAX_CARDS_SHOWN - len(pd_legals)}'
    pd_illegals = str(fetch_tools.fetch(url3)).split('\n')
    return count, pd_legals + pd_illegals

def more_results_link(args: str, total: int) -> str:
    return 'and {n} more.\n<{d}/cards/find?q={q}>'.format(
        n=total - 4, q=fetch_tools.escape(args), d=link_domain) if total > MAX_CARDS_SHOWN else ''
