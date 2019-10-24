import re
from typing import Dict, Optional

from discord.ext import commands

from discordbot.command import MtgContext, roughly_matches
from magic import fetcher


@commands.command(aliases=['res', 'pdm'])
async def resources(ctx: MtgContext, *, args: Optional[str]) -> None:
    """Useful pages related to `args`. Examples: 'tournaments', 'card Naturalize', 'deckcheck', 'league'."""
    results = {}
    if args is None:
        args = ''
    if len(args) > 0:
        results.update(resources_resources(args))
        results.update(site_resources(args))
    s = ''
    if len(results) == 0:
        s = 'PD resources: <{url}>'.format(url=fetcher.decksite_url('/resources/'))
    elif len(results) > 10:
        s = '{author}: Too many results, please be more specific.'.format(author=ctx.author.mention)
    else:
        for url, text in results.items():
            s += '{text}: <{url}>\n'.format(text=text, url=url)
    await ctx.send(s)

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
        detail = '{detail}/'.format(
            detail=fetcher.internal.escape(detail, True)) if detail else ''
        url = fetcher.decksite_url('{season_prefix}/{area}/{detail}'.format(
            season_prefix=season_prefix, area=fetcher.internal.escape(area), detail=detail))
        results[url] = args
    return results


def resources_resources(args: str) -> Dict[str, str]:
    results = {}
    words = args.split()
    for title, items in fetcher.resources().items():
        for text, url in items.items():
            asked_for_this_section_only = len(
                words) == 1 and roughly_matches(title, words[0])
            asked_for_this_section_and_item = len(words) == 2 and roughly_matches(
                title, words[0]) and roughly_matches(text, words[1])
            asked_for_this_item_only = len(
                words) == 1 and roughly_matches(text, words[0])
            the_whole_thing_sounds_right = roughly_matches(
                text, ' '.join(words))
            the_url_matches = roughly_matches(url, ' '.join(words))
            if asked_for_this_section_only or asked_for_this_section_and_item or asked_for_this_item_only or the_whole_thing_sounds_right or the_url_matches:
                results[url] = text
    return results
