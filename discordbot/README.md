
# Penny-Dreadful-Discord-Bot
Displays info about quoted cards in a discord channel

[![Build Status](http://ci.katelyngigante.com/buildStatus/icon?job=Penny Dreadful/Penny-Dreadful-Tools/master)](http://ci.katelyngigante.com/job/Penny%20Dreadful/job/Penny-Dreadful-Tools/job/master/)
[![Bot Issues](https://badge.waffle.io/PennyDreadfulMTG/Penny-Dreadful-Discord-Bot.svg?label=bot&title=Issues)](http://waffle.io/PennyDreadfulMTG/Penny-Dreadful-Tools)


#Usage
Basic bot usage: Include [cardname] in your regular messages.

The bot will search for any quoted cards, and respond with the card details.

#Commands


`!oracle {name}` Give the Oracle text of the named card.

`!barbs` Gives Volvary's helpful advice for when to sideboard in Aura Barbs.

`!bug` Report a bug

`!help` Provides information on how to operate the bot.

`!legal` Announce whether the specified card is legal or not.

`!modofail` Ding!

`!price {name}` Get price information about the named card.

`!quality` A helpful reminder about everyone's favorite way to play digital Magic

`!random` Request a random PD legal card

`!random X` Request X random PD legal cards.

`!resources` Link to page of all Penny Dreadful resources.

           `!resources {section}` Link to Penny Dreadful resources section.

           `!resources {section} {link}` Link to Penny Dreadful resource.

        

`!rhinos` Anything can be a rhino if you try hard enough

`!rotation` Give the date of the next Penny Dreadful rotation.

`!search {query}` Search for cards, using a magidex style query.

`!spoiler` !spoiler {cardname}: Request a card from an upcoming set

`!status` Gives the status of MTGO, UP or DOWN.

# Developer Commands

`!clearimagecache` Deletes all the cached images.  Use sparingly

`!echo` Repeat after me...

`!restartbot` Restarts the bot.

`!update` Forces an update to the legal card list

#Installation
To add this bot to your servers use this <a href='https://discordapp.com/oauth2/authorize?client_id=224755717767299072&scope=bot&permissions=0'>link</a>

#Libraries used

[Discord.py](https://github.com/Rapptz/discord.py)

[mtgjson](http://mtgjson.com/)
