from mtgsdk import Card
import json
com = input(': ')
def reduce(str_input):
	return '-'.join(str_input.split(' ')).lower()
def http_address(set,name):
	return 'http://store.tcgplayer.com/magic/'+reduce(set)+'/'+reduce(name)
def http_parse(str_input):
	return '%20'.join(str_input.split(' '))
if com.startswith('!magic'):
	msg_com = com.split('-')
	msg_com.pop(0)
	for msg in msg_com:
		if 'help' in msg.lower():
			print('help')
		elif 'm' in msg.lower():
			print(msg[2:])
			card_m = Card.find(msg[2:])
			print(http_address(card_m.set_name,card_m.name))
		elif 's' in msg.lower():
			print(msg[2:])
			card_s = Card.where(name=http_parse(msg[2:])).all()
			for s_card in card_s:
				print(s_card.name)
