import re

from interactions.models.internal import OptionType, auto_defer, slash_command, slash_option

from discordbot.command import MtgInteractionContext, roughly_matches
from magic import fetcher
from shared import fetch_tools


@slash_command('resources')
@slash_option('resource', 'Your query', OptionType.STRING)
@auto_defer()
async def resources(ctx: MtgInteractionContext, resource: str | None) -> None:
    """Useful pages related to `args`."""
    results = {}
    if resource is None:
        resource = ''
    if len(resource) > 0:
        results.update(resources_resources(resource))
        results.update(site_resources(resource))
    s = ''
    if len(results) == 0:
        s = "Sorry, I don't know about that.\nPD resources: <{url}>".format(url=fetcher.decksite_url('/resources/'))
    elif len(results) > 10:
        s = f'{ctx.author.mention}: Too many results, please be more specific.'
    else:
        for url, text in results.items():
            s += f'{text}: <{url}>\n'
    await ctx.send(s)

def site_resources(args: str) -> dict[str, str]:
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
    matches = [endpoint for endpoint in sitemap if endpoint.startswith(f'/{area}/')]
    if len(matches) > 0:
        detail = '{detail}/'.format(
            detail=fetch_tools.escape(detail, True),
        ) if detail else ''
        url = fetcher.decksite_url(
            '{season_prefix}/{area}/{detail}'.format(
            season_prefix=season_prefix, area=fetch_tools.escape(area), detail=detail,
            ),
        )
        results[url] = args
    return results


def resources_resources(args: str) -> dict[str, str]:
    results = {}
    words = args.split()
    for title, items in fetcher.resources().items():
        for text, url in items.items():
            asked_for_this_section_only = len(
                words,
            ) == 1 and roughly_matches(title, words[0])
            asked_for_this_section_and_item = len(words) == 2 and roughly_matches(
                title, words[0],
            ) and roughly_matches(text, words[1])
            asked_for_this_item_only = len(
                words,
            ) == 1 and roughly_matches(text, words[0])
            the_whole_thing_sounds_right = roughly_matches(
                text, ' '.join(words),
            )
            the_url_matches = roughly_matches(url, ' '.join(words))
            if asked_for_this_section_only or asked_for_this_section_and_item or asked_for_this_item_only or the_whole_thing_sounds_right or the_url_matches:
                results[url] = text
    return results
