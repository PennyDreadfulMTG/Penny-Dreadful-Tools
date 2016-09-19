from mtgsdk import Card
import json, discord, os, string
import urllib.request

prop = {'name','multiverse_id','layout','names','mana_cost','cmc','colors','type','supertypes','subtypes','rarity','text','flavor','artist','number','power','toughness','loyalty','variations','watermark','border','timeshifted','hand','life','reserved','release_date','starter','rulings','foreign_names','printings','original_text','original_type','legalities','source','image_url','set','set_name','id'}
run = 'card_adv = Card'
def adv(str_input):
	return '='.join(str_input.split(' ')).lower()
def reduce(str_input):
	return '-'.join(str_input.split(' ')).lower()
def http_image(uid):
	return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(uid)  +'.jpg'
def http_address(set,name):
	return 'http://store.tcgplayer.com/magic/'+reduce(set)+'/'+reduce(name)
def http_parse(str_input):
	return '%20'.join(str_input.split(' '))


legalcards = urllib.request.urlopen('http://pdmtgo.com/legal_cards.txt').readlines() 

print("Legal cards: " + str(len(legalcards)))

client = discord.Client()

@client.event
async def on_message(message):
        # we do not want the bot to reply to itself
        if message.author == client.user:
                return
        print(message.content)
        content = message.content
        end = len(content)
        start = content.find("[") + 1
        while start > 0:
          # ss1 = content[ouvert: end]
          end = content.find("]", start)
          search = content[start: end].strip('[ ')
          print("Request : " + search)
          if len(search) > 2:
             cards = Card.where(name=search).all()
             for card in cards:
                 if card.type=="Vanguard":
                   continue
                 if not card.multiverse_id:
                   continue
                 if not card.name.startswith(search):
                   continue
                 resp = string.Template("$name $mana_cost — $type \n$text").substitute(name=card.name, mana_cost=card.mana_cost if card.mana_cost else '', type=card.type, text=card.text)
                 await client.send_message(message.channel, resp)
                 print(http_image(card.multiverse_id))
                 await client.send_message(message.channel,http_image(card.multiverse_id))
                 if card.name in legalcards:
                   await client.send_message(message.channel,"Legal in Penny Dreadful :white_check_mark:")
                 else:
                   await client.send_message(message.channel,"Illegal in Penny Dreadful :negative_squared_cross_mark:")
                 break

          start = content.find("[", end) + 1


@client.event
async def on_ready():
	print('Logged in as')
	print(client.user.name)
	print(client.user.id)
	print('------')
client.run(os.environ['TOKEN'])
