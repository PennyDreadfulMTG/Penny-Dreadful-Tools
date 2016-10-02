import bot

BOT = bot.Bot()

# Because of the way discord.py works I can't work out how to decorate instance methods.
# Thus we stub on_message and on_ready here and pass to Bot to do the real work.

@BOT.client.event
async def on_message(message):
    await BOT.on_message(message)

@BOT.client.event
async def on_ready():
    await BOT.on_ready()

BOT.init()
