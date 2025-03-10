import functools

from github import Github
from github.Repository import Repository
from interactions import Client
from interactions.models import Button, Embed, Extension, slash_command

from discordbot import command
from discordbot.command import MtgContext, MtgInteractionContext
from magic import fetcher
from magic.models import Card
from shared import configuration, fetch_tools
from shared.custom_types import BugData, ForumData
from shared.pd_exception import OperationalException


class ModoBugs(Extension):
    """Commands for interacting with the modo-bugs repository."""
    blacklist: set[tuple[str, str]] = set()

    @slash_command('modo-bug')
    async def modobug(self, _ctx: MtgInteractionContext) -> None:
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
        await ctx.defer()
        bugs = await fetcher.bugged_cards_async()
        forums = await fetcher.daybreak_forums_async()
        if not bugs or not forums:
            return
        for b in bugs:
            if b['support_thread'] is None:
                for f in forums.values():
                    if f['tracked']:
                        continue
                    if (b['url'], f['url']) in self.blacklist:
                        continue
                    if b['card'] in f['title']:
                        e = Embed(b['description'], b['url'] + '\n\n' + f['url'] + f'  [{f["status"]}]')
                        yes = Button(label='These are the same issue', emoji='✅', style=3)
                        no = Button(label='These are different issues', emoji='❌', style=4)
                        msg = await ctx.send(embed=e, components=[yes, no])
                        on_pressed = await self.bot.wait_for_component(msg, components=[yes, no], timeout=None)  # type: ignore
                        await msg.edit(components=[])
                        pressed = on_pressed.ctx
                        if yes.custom_id == pressed.custom_id:
                            issue = get_repo().get_issue(b['issue_number'])
                            if issue is None:
                                continue
                            issue.edit(body=issue.body + '\n\n' + f['url'])
                        elif no.custom_id == pressed.custom_id:
                            self.blacklist.add((b['url'], f['url']))

    @modobug.subcommand('lookup')
    @command.slash_card_option()
    async def buglink(self, ctx: MtgContext, card: Card) -> None:
        """Link to the modo-bugs page for a card."""
        base_url = 'https://github.com/PennyDreadfulMTG/modo-bugs/issues'
        if card is None:
            await ctx.send(base_url)
            return
        msg = f'<{base_url}?utf8=%E2%9C%93&q=is%3Aissue+%22{fetch_tools.escape(card.name)}%22>'
        await ctx.send(msg)


def format_bug(bug: BugData) -> str:
    return f'[{bug["description"]}]({bug["url"]})'

def format_post(post: ForumData) -> str:
    return f'[{post["title"]}]({post["url"]})'

def valid_thread(post: ForumData) -> bool:
    if post['tracked']:
        return False
    if post['status'] in ['Fixed', 'Not A Bug']:
        return False
    return True

@functools.lru_cache
def get_github() -> Github | None:
    if not configuration.get_str('github_user') or not configuration.get_str('github_password'):
        return None
    return Github(configuration.get_str('github_user'), configuration.get_str('github_password'))

@functools.lru_cache
def get_repo() -> Repository:
    gh = get_github()
    if gh is not None:
        return gh.get_repo('PennyDreadfulMTG/modo-bugs')
    raise OperationalException

def setup(bot: Client) -> None:
    ModoBugs(bot)
