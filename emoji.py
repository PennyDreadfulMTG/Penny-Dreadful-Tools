import discord
import database
import re

db = database.Database()

def FindEmoji(emoji, channel):
    if channel.is_private:
        return None
    try:
        emojis = channel.server.emojis
        return next((x for x in emojis if x.name == emoji), None)
    except AttributeError:
        return None

def ReplaceEmoji(text, channel):
    if channel.is_private:
        return text

    output = text
    symbols = re.findall(r'\{([A-Z0-9/]{1,3})\}', text)
    for symbol in symbols:
        name = symbol
        name = name.replace('/','')
        if len(name) == 1:
            if re.fullmatch("[0-9]", name):
                name = "0" + name
            else:
                name = name + name
        emoji = FindEmoji(name, channel)
        if emoji != None:
            output = output.replace("{" + symbol + "}", str(emoji))
    return output