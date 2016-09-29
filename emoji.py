import discord
import database
import re

db = database.Database()

def FindEmoji(emoji, channel):
  if channel.is_private:
    return None
  emojis = channel.server.emojis
  return next((x for x in emojis if x.name == emoji), None)

def ReplaceEmoji(text, channel):
  if channel.is_private:
    return text
  
  output = text
  symbols = re.findall(r'\{([A-Z0-9/]{1,3})\}', text)
  for symbol in symbols:
    name = symbol
    name.replace('/','')
    if len(name) == 1:
      name = name + name
    emoji = FindEmoji(name, channel)
    if emoji != None:
      output = output.replace("{" + symbol + "}", str(emoji))
  return output