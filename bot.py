from mtgsdk import Card
import json, discord
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
client = discord.Client()
@client.event
async def on_message(message):
        # we do not want the bot to reply to itself
        if message.author == client.user:
                return
        if message.content.startswith('!magic'):
                msg_com = message.content.split('-')
                msg_com.pop(0)
                for msg in msg_com:
                        if '-help' in msg.lower():
                                print('help')
                                await client.send_message(message.channel,'Magic Card Bot \n --help : This message displaying \n -s_reg : Followed by a string will search that string \n -m_uid : Searchs cards by multivesrse id \n -s_adv : Not currently finished')
                        elif 'm_uid' in  msg.lower():
                                print(msg[6:])
                                card_m = Card.find(msg[6:])
                                print(http_address(card_m.set_name,card_m.name))
                                await client.send_message(message.channel,http_address(card_m.set_name,card_m.name))
                                print(http_image(card_m.multiverse_id))
                                await client.send_message(message.channel,http_image(card_m.multiverse_id))
                        elif 's_reg' in msg.lower():
                                print(http_parse(msg[6:]))
                                card_s = Card.where(name=msg[6:]).all()
                                for s_card in card_s:
                                        print(http_address(s_card.set_name,s_card.name))
                                        await client.send_message(message.channel,http_address(s_card.set_name,s_card.name))
                                        print(http_image(s_card.multiverse_id))
                                        await client.send_message(message.channel,http_image(s_card.multiverse_id))
                        elif 's_adv' in msg.lower():
                                await client.send_message(message.channel,'This command is disabled')
                        else:
                                print('RIP something went wrong')
                                await client.send_message(message.channel, 'RIP something went wrong')
@client.event
async def on_ready():
	print('Logged in as')
	print(client.user.name)
	print(client.user.id)
	print('------')
client.run('Bot Token')
