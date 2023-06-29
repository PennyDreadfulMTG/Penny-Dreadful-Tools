from naff.models import Embed, Extension, slash_command, Button

from discordbot import command
from discordbot.command import MtgContext, MtgInteractionContext
from magic import fetcher
from magic.models import Card
from shared import fetch_tools
from modo_bugs import repo


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
            needs_issue = [p for p in forums.values() if valid_thread(p)]
            if needs_issue:
                embeds.append(Embed('Needs Issue', '\n'.join(format_post(p) for p in needs_issue[:5]), footer='Either Associate this thread with our issue, or make one'))

        await ctx.send(embeds=embeds)

    @modobug.subcommand('queue')
    async def queue(self, ctx: MtgInteractionContext) -> None:
        """Triage unmapped forum threads"""
        bugs = await fetcher.bugged_cards_async()
        forums = await fetcher.daybreak_forums_async()
        if not bugs or not forums:
            return
        for b in bugs:
            if b['support_thread'] is None:
                for f in forums.values():
                    if f['tracked']:
                        continue

                    if b['card'] in f['title']:
                        e = Embed(b['description'], b['url'] + '\n\n' + f['url'] + f'  [{f["status"]}]')
                        yes = Button(label='These are the same issue', emoji='✅', style=3)
                        no = Button(label='These are different issues', emoji='❌', style=4)
                        msg = await ctx.send(embed=e, components=[yes, no])
                        on_pressed = await self.bot.wait_for_component(msg, components=[yes, no], timeout=None)
                        await msg.edit(components=[])
                        pressed = on_pressed.ctx
                        if yes.custom_id == pressed.custom_id:
                            issue = repo.get_repo().get_issue(b['issue_number'])
                            if issue is None:
                                continue
                            issue.edit(body=issue.body + '\n\n' + f['url'])
                        elif no.custom_id == pressed.custom_id:
                            pass


    # @modobug.subcommand('still-bugged')
    # async def still(self, ctx: MtgInteractionContext) -> None:
    #     """Report updated bugs"""

    @modobug.subcommand('lookup')
    @command.slash_card_option()
    async def buglink(self, ctx: MtgContext, card: Card) -> None:
        """Link to the modo-bugs page for a card."""
        base_url = 'https://github.com/PennyDreadfulMTG/modo-bugs/issues'
        if card is None:
            await ctx.send(base_url)
            return
        msg = '<{base_url}?utf8=%E2%9C%93&q=is%3Aissue+%22{name}%22>'.format(base_url=base_url, name=fetch_tools.escape(card.name))
        await ctx.send(msg)

    buglink.autocomplete('card')(command.autocomplete_card)  # type: ignore


def format_bug(bug: dict[str, str]) -> str:
    return f'[{bug["description"]}]({bug["url"]})'

def format_post(post: dict[str, str]) -> str:
    return f'[{post["title"]}]({post["url"]})'

def valid_thread(post: dict[str, str]) -> bool:
    if post['tracked']:
        return False
    if post['status'] in ['Fixed', 'Not A Bug']:
        return False
    return True
