import random
import sys

import bot
import fetcher


async def handle_command(message):
    global STATE
    STATE = bot.STATE
    parts = message.content.split(' ', 1)
    cmd = parts[0].lstrip('!').lower()
    args = ""
    if len(parts) > 1:
        args = parts[1]

    method = [m for m in dir(Commands) if m == cmd]
    if len(method) > 0:
        await getattr(Commands, method[0])(Commands, message.channel, args)
    else:
        await STATE.client.send_message(message.channel, 'Unknown command `{cmd}`. Try `!help`?'.format(cmd=cmd))
    

class Commands:
    
    async def help(self, channel, args):
        """`!help` Get this message."""
        msg = """Basic bot usage: Include [cardname] in your regular messages.
The bot will search for any quoted cards, and respond with the card details.

Addiional Commands:"""
        for methodname in dir(Commands):
            if methodname.startswith("__"):
                continue
            method = getattr(self, methodname)
            if method.__doc__:
                msg += '\n{0}'.format(method.__doc__)
        msg += """

Have any Suggesions/Bug Reports? Submit them here: https://github.com/PennyDreadfulMTG/Penny-Dreadful-Discord-Bot/issues
Want to contribute? Send a Pull Request."""
        await bot.STATE.client.send_message(channel, msg)

    async def random(self,channel,args):
        """`!Random` Request a random PD legal card
`!random X` Request X random PD legal cards."""
        number = 1
        if len(args) > 0:
            try:
                number = int(args.strip())
            except ValueError:
                pass
        cards = [STATE.oracle.search(random.choice(STATE.legal_cards))[0] for n in range(0, number)]
        await bot.post_cards(cards, channel)

    async def reload(self,channel,args):
        bot.update_legality()
        await STATE.client.send_message(channel, 'Reloaded list of legal cards.')

    async def restartbot(self,channel,args):
        await STATE.client.send_message(channel, 'Rebooting!')
        sys.exit()

    async def search(self,channel,args):
        """`!search query` Search for cards, using a magidex style query."""
        cards = bot.complex_search(args)
        await bot.post_cards(cards, channel)
        if len(cards) > 10:
            await STATE.client.send_message(channel, 'http://magidex.com/search/?q=' + bot.escape(q))

    async def showall(self,channel,args):
        """`!showall` Show all the cards relating to a query.  Only available if you PM the bot."""
        cards = bot.complex_search(args)
        more_text = ''
        text = ', '.join('{name} {legal}'.format(name=card.name, legal=bot.legal_emoji(card)) for card in cards)
        text += more_text
        image_file = bot.download_image(cards)
        if image_file is None:
            text += '\n\n'
            text += 'No image available.'
            await STATE.client.send_message(channel, text)
        else:
            await STATE.client.send_file(channel, image_file, content=text)

    async def status(self,channel,args):
        """`!status` Gives the status of MTGO, UP or DOWN."""
        status = fetcher.mtgo_status()
        await STATE.client.send_message(channel, 'MTGO is {status}'.format(status=status))


    async def echo(self,channel,args):
        s = args
        s = bot.emoji.replace_emoji(s, channel)
        print('Echoing {s}'.format(s=s))
        await STATE.client.send_message(channel, s)

    async def barbs(self,channel,args):
        """`!barbs` Gives Volvary's helpful advice for when to sideboard in Aura Barbs."""
        msg = "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."
        await STATE.client.send_message(channel, msg)
    
    async def quality(self,channel,args):
        """A helpful reminder about everyone's favorite way to play digital Magic"""
        msg = "**Magic Online** is a Quality™ Program."
        await STATE.client.send_message(channel, msg)
