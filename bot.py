import urllib.request, discord, json
client = discord.Client()
@client.event
async def on_message(message):
    # we do not want the bot to reply to itself
    if message.author == client.user:
        return
    if message.content.startswith('!magic'):
        msg_com = message.content.split('-')
        msg_com.pop(0)
        for com in msg_com:
            if "help" in com.lower():
                await client.send_message(message.channel,'Magic Card Bot \n -help : This message displaying \n -search : Followed by a int string will search that string \n -id : Searchs cards by number')
                break
            elif "id" in com.lower():
                print(com.lower().replace('search ',''))
                request = 'https://api.deckbrew.com/mtg/cards?multiverseid=' + com[3:]
                data = urllib.request.urlopen(request).read().decode()
                data = "".join(data.split('\\"'))
                data = json.loads(data[1:-1])
                data = json.loads(json.dumps(data['editions'][0]))
                print(data['url'])
                await client.send_message(message.channel, data['store_url'])
                await client.send_message(message.channel, data['image_url'])
            elif "search" in com.lower():
                request = 'https://api.deckbrew.com/mtg/cards?name=' + com[7:].replace(" ","%20")
                data = urllib.request.urlopen(request).read().decode()
                data = "".join(data.split('\\"'))
                data = json.loads(data[1:-1])
                data = json.loads(json.dumps(data['editions'][0]))
                await client.send_message(message.channel, data['store_url'])
                await client.send_message(message.channel, data['image_url'])
            else:
                print('RIP something went wrong')
                await client.send_message(message.channel, 'RIP something went wrong')
@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
client.run('MjA5MDMzODQ1OTY0NTM3ODU3.Cn6VcA.3sw_-8FWPmLtMj8rJNrE0fPPVI8')
