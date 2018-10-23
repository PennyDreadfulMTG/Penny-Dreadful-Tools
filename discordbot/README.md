
# Penny-Dreadful-Discord-Bot
Displays info about quoted cards in a discord channel

[![Build Status](http://ci.katelyngigante.com/buildStatus/icon?job=Penny Dreadful/Penny-Dreadful-Tools/master)](http://ci.katelyngigante.com/job/Penny%20Dreadful/job/Penny-Dreadful-Tools/job/master/)
[![Bot Issues](https://badge.waffle.io/PennyDreadfulMTG/Penny-Dreadful-Discord-Bot.svg?label=bot&title=Issues)](http://waffle.io/PennyDreadfulMTG/Penny-Dreadful-Tools)


#Usage
Basic bot usage: Include [cardname] in your regular messages.

The bot will search for any quoted cards, and respond with the card details.

#Commands


`!oracle {name}` Give the Oracle text of the named card.

`!art {name}` Display the art (only) of the most recent printing of the named card.

`!barbs` Gives Volvary's helpful advice for when to sideboard in Aura Barbs.

`!bug` Report a bug/task for the Penny Dreadful Tools team. For Magic Online bugs see `!modobug`.

`!buglink` Get a link to the modo-bugs page for the named card.

`!explain`. Get a list of things the bot knows how to explain.

`!explain {thing}`. Print commonly needed explanation for 'thing'.

`!gbug` Report a Gatherling bug.

`!google {args}` Search google for `args`.

`!help` Provides information on how to operate the bot.

`!history` Show the legality history of the specified card and a link to its all time page.

`!invite` Invite me to your server.

`!legal` Announce whether the specified card is legal or not.

`!modobug` Report a Magic Online bug.

`!modofail` Ding!

`!pdm` Alias for `!resources`.

`!price {name}` Get price information about the named card.

`!quality` A helpful reminder about everyone's favorite way to play digital Magic

`!random` Request a random PD legal card.

`!random X` Request X random PD legal cards.

`!resources {args}` Link to useful pages related to `args`. Examples: 'tournaments', 'card Hymn to Tourach', 'deck check', 'league'.

`!rhinos` Anything can be a rhino if you try hard enough

`!rotation` Give the date of the next Penny Dreadful rotation.

`!rulings {name}` Display rulings for a card.

`!search {query}` Search for cards, using a scryfall-style query.

`!spoiler {cardname}`: Request a card from an upcoming set.

`!status` Gives the status of Magic Online: UP or DOWN.

`!time {location}` Show the current time in the specified location.

`!tournament` Get information about the next tournament.

# Aliases

`!scryfall {query}` Alias for `!search`.

# Developer Commands

`!clearimagecache` Deletes all the cached images.  Use sparingly

`!echo` Repeat after me…

`!notpenny` Don't show PD Legality in this channel

`!restartbot` Restarts the bot.

`!update` Forces an update to legal cards and bugs.

`!version` Display the current version numbers

#Installation
To add this bot to your servers use this <a href='https://discordapp.com/oauth2/authorize?client_id=224755717767299072&scope=bot&permissions=0'>link</a>

#Libraries used

[Discord.py](https://github.com/Rapptz/discord.py)

[mtgjson](https://mtgjson.com/)
