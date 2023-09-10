from interactions.models import slash_command

from discordbot.command import MtgContext
from shared import redis_wrapper as redis


@slash_command('modofail')
async def modofail(ctx: MtgContext) -> None:
    """Ding!"""
    # author = ctx.author
    # if isinstance(author, Member) and hasattr(author, 'voice') and author.voice is not None and author.voice.channel is not None:
    #     voice_channel = ctx.author.voice.channel
    #     voice = ctx.channel.guild.voice_client
    #     if voice is None:
    #         voice = await voice_channel.connect()
    #     elif voice.channel != voice_channel:
    #         voice.move_to(voice_channel)
    #     voice.play(FFmpegPCMAudio('ding.ogg'))
    n = redis.increment(f'modofail:{ctx.guild}')
    redis.expire(f'modofail:{ctx.guild}', 3600)
    await ctx.send(f':bellhop: **MODO fail** {n}')
