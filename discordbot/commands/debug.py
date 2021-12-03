"""
This scale provides basic debug information about the current state of the bot.
"""

import datetime
import io
import platform
import textwrap
import traceback
from collections import Counter
from contextlib import redirect_stdout
from dis_snek.client import Snake

from dis_snek.const import __version__, __py_version__
from dis_snek.errors import CommandCheckFailure, ScaleLoadException
from dis_snek.models import (
    slash_command,
    InteractionContext,
    Embed,
    message_command,
    MessageContext,
    check,
    MaterialColors,
    Timestamp,
)
from dis_snek.models.checks import is_owner
from dis_snek.models.context import Context
from dis_snek.models.enums import Intents
from dis_snek.models.scale import Scale
from dis_snek.utils.cache import TTLCache


def strf_delta(time_delta: datetime.timedelta, show_seconds: bool = True) -> str:
    """Formats timedelta into a human readable string"""
    years, days = divmod(time_delta.days, 365)
    hours, rem = divmod(time_delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    years_fmt = f"{years} year{'s' if years > 1 or years == 0 else ''}"
    days_fmt = f"{days} day{'s' if days > 1 or days == 0 else ''}"
    hours_fmt = f"{hours} hour{'s' if hours > 1 or hours == 0 else ''}"
    minutes_fmt = f"{minutes} minute{'s' if minutes > 1 or minutes == 0 else ''}"
    seconds_fmt = f"{seconds} second{'s' if seconds > 1 or seconds == 0 else ''}"

    if years >= 1:
        return f"{years_fmt} and {days_fmt}"
    if days >= 1:
        return f"{days_fmt} and {hours_fmt}"
    if hours >= 1:
        return f"{hours_fmt} and {minutes_fmt}"
    if show_seconds:
        return f"{minutes_fmt} and {seconds_fmt}"
    return f"{minutes_fmt}"


class DebugScale(Scale):
    def D_Embed(self, title: str) -> Embed:
        e = Embed(
            f"Dis-Snek Debug: {title}",
            url="https://github.com/LordOfPolls/Rebecca/blob/master/scales/debug.py",
            color=MaterialColors.BLUE_GREY,
        )
        e.set_footer(
            "Dis-Snek Debug Scale",
            icon_url="https://avatars.githubusercontent.com/u/91958504?s=200&v=4",
        )
        return e

    @slash_command(
        "debug",
        sub_cmd_name="info",
        sub_cmd_description="Get basic information about the bot",
    )
    async def debug_info(self, ctx: InteractionContext) -> None:
        await ctx.defer()

        uptime = datetime.datetime.now() - self.bot.start_time
        e = self.D_Embed("General")
        e.set_thumbnail(self.bot.user.avatar.url)
        e.add_field("Operating System", platform.platform())

        e.add_field("Version Info", f"Dis-Snek@{__version__} | Py@{__py_version__}")

        e.add_field(
            "Start Time",
            f"{Timestamp.fromdatetime(self.bot.start_time)}\n({strf_delta(uptime)} ago)",
        )

        privileged_intents = [
            i.name for i in self.bot.intents if i in Intents.PRIVILEGED
        ]
        if privileged_intents:
            e.add_field("Privileged Intents", " | ".join(privileged_intents))

        e.add_field("Loaded Scales", ", ".join(self.bot.scales))

        e.add_field("Guilds", str(len(self.bot.guilds)))

        await ctx.send(embeds=[e])

    @debug_info.subcommand(
        "cache", sub_cmd_description="Get information about the current cache state"
    )
    async def cache_info(self, ctx: InteractionContext) -> None:
        await ctx.defer()
        e = self.D_Embed("Cache")
        e.description = ""
        caches = [
            "channel_cache",
            "dm_channels",
            "guild_cache",
            "member_cache",
            "message_cache",
            "role_cache",
            "user_cache",
        ]

        for cache in caches:
            val = getattr(self.bot.cache, cache)
            if isinstance(val, TTLCache):
                e.description += f"\n`{cache}`: {len(val)} / {val.hard_limit}({val.soft_limit}) ttl:`{val.ttl}`s"
            else:
                e.description += f"\n`{cache}`: {len(val)} / ∞ (no_expire)"

        await ctx.send(embeds=[e])

    @debug_info.subcommand(
        "cmds", sub_cmd_description="Get Information about registered app commands",
    )
    async def app_cmd(self, ctx: InteractionContext) -> None:
        await ctx.defer()
        e = self.D_Embed("Application-Commands")

        cmds = 0
        for v in self.bot.interactions.values():
            for cmd in v.values():
                # if cmd.subcommands:
                #     cmds += len(cmd.subcommands)
                #     continue
                cmds += 1

        e.add_field("Local application cmds (incld. Subcommands)", str(cmds))
        e.add_field("Component callbacks", str(len(self.bot._component_callbacks)))
        e.add_field("Message commands", str(len(self.bot.commands)))
        e.add_field(
            "Tracked Scopes",
            str(
                len(
                    Counter(
                        scope for scope in self.bot._interaction_scopes.values()
                    ).keys()
                )
            ),
        )

        await ctx.send(embeds=[e])

    @message_command("exec")
    @check(is_owner)
    async def debug_exec(self, ctx: MessageContext) -> None:
        await ctx.channel.trigger_typing()
        body = ctx.message.content.removeprefix(
            f"{await self.bot.get_prefix(ctx.message)}{ctx.invoked_name} "
        )
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "server": ctx.guild,
            "guild": ctx.guild,
            "message": ctx.message,
        } | globals()
        if body.startswith("```") and body.endswith("```"):
            body = "\n".join(body.split("\n")[1:-1])
        else:
            body = body.strip("` \n")

        stdout = io.StringIO()

        to_compile = "async def func():\n%s" % textwrap.indent(body, "  ")
        try:
            exec(to_compile, env)
        except SyntaxError:
            return await ctx.send("```py\n{}\n```".format(traceback.format_exc()))

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            return await ctx.send(
                "```py\n{}{}\n```".format(value, traceback.format_exc())
            )
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction("\u2705")
            except:
                pass

            if ret is None:
                if value:
                    try:
                        await ctx.message.reply("```py\n%s\n```" % value)
                    except:
                        await ctx.send("```py\n%s\n```" % value)
            else:
                try:
                    await ctx.message.reply("```py\n%s%s\n```" % (value, ret))
                except:
                    await ctx.send("```py\n%s%s\n```" % (value, ret))

    @debug_exec.error
    async def exec_error(self, error: Exception, ctx: Context) -> None:
        if isinstance(error, CommandCheckFailure):
            return await ctx.send("You do not have permission to execute this command")
        raise

    @message_command('regrow')
    @check(is_owner)
    async def regrow(self, ctx: MessageContext, module: str) -> None:
        try:
            self.bot.regrow_scale(f'discordbot.commands.{module}')
            ctx.message
        except ScaleLoadException as e:
            if 'Unable to shed scale: No scale exists with name' in str(e):
                try:
                    self.bot.grow_scale(f'discordbot.commands.{module}')

                except ScaleLoadException as c:
                    await ctx.send(c)
            else:
                await ctx.send(e)

    @regrow.error
    async def regrow_error(self, error: Exception, ctx: Context) -> None:
        if isinstance(error, CommandCheckFailure):
            return await ctx.send("You do not have permission to execute this command")
        raise


def setup(bot: Snake) -> None:
    DebugScale(bot)
