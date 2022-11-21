from naff.models import slash_command, Extension, Embed

from discordbot.command import MtgContext, MtgInteractionContext
from magic import fetcher


class ModoBugs(Extension):
    @slash_command('modo-bug')
    async def modobug(self) -> None:
        """Our Magic Online Bug Tracker."""

    @modobug.subcommand('report')
    async def report(self, ctx: MtgContext) -> None:
        """Report a Magic Online bug"""
        await ctx.send('Report Magic Online issues at <https://github.com/PennyDreadfulMTG/modo-bugs/issues/new/choose>. Please follow the instructions there. Thanks!')

    @modobug.subcommand('triage')
    async def triage(self, ctx: MtgInteractionContext) -> None:
        """Some things your can do to help"""
        bugs = await fetcher.bugged_cards_async()
        forums = await fetcher.daybreak_forums_async()

        embeds = []

        if bugs:
            needs_testing = [b for b in bugs if b['last_verified'] is None]
            if needs_testing:
                embeds.append(Embed('Needs Testing', '\n'.join(format_bug(b) for b in needs_testing[:5]), footer='Play a game with these cards, and use !stillbugged or !notbugged'))

            needs_reporting = [b for b in bugs if b['support_thread'] is None]
            if needs_reporting:
                embeds.append(Embed('Needs Support Thread', '\n'.join(format_bug(b) for b in needs_reporting[:5]), footer='Check if the Daybreak Forums have a thread on this bug, and add a link to it'))

        if forums:
            needs_issue = [p for p in forums.values() if not p['tracked']]
            if needs_issue:
                embeds.append(Embed('Needs Issue', '\n'.join(format_post(p) for p in needs_issue[:5]), footer='Either Associate this thread with our issue, or make one'))

        await ctx.send(embeds=embeds)

    # @modobug.subcommand('still-bugged')
    # async def still(self, ctx: MtgInteractionContext) -> None:
    #     """Report updated bugs"""


def format_bug(bug: dict[str, str]) -> str:
    return f'[{bug["description"]}]({bug["url"]})'

def format_post(post: dict[str, str]) -> str:
    return f'[{post["title"]}]({post["url"]})'
