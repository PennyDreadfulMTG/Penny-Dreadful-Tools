from dis_snek import Snake
from dis_snek.models.application_commands import OptionTypes, slash_command, slash_option
from dis_snek.models.command import message_command
from dis_snek.models.scale import Scale

from discordbot.command import MtgContext
from shared import repo

class Bug(Scale):
    @slash_command('bug')
    @slash_option('title', 'One sentence description of the issue', OptionTypes.STRING)
    async def bug(self, ctx: MtgContext, title: str) -> None:
        """Report a bug/task for the Penny Dreadful Tools team. For Magic Online bugs see `/modobug`."""
        issue = repo.create_issue(title, ctx.author)
        if issue is None:
            await ctx.send('Report issues at <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/new>')
        else:
            await ctx.send('Issue has been reported at <{url}>'.format(url=issue.html_url))


def setup(bot: Snake) -> None:
    Bug(bot)
