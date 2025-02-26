import time
from collections import defaultdict

from interactions.client.utils import TTLItem
from interactions.models import Extension, slash_command

from discordbot.command import MtgContext
from magic import fetcher
from shared import configuration
from shared.container import Container

TTL = 30 * 60

class MosLeague(Extension):
    queues: defaultdict[int, list[TTLItem[int]]] = defaultdict(list)

    @slash_command(scopes=[711238742270017547])
    async def queue(self, ctx: MtgContext) -> None:
        pass

    @queue.subcommand(sub_cmd_name='join', sub_cmd_description='Join the queue')
    async def queue_join(self, ctx: MtgContext) -> None:
        tournament_channel_id = configuration.get_int('mos_premodern_channel_id')
        if ctx.channel_id != tournament_channel_id:
            await ctx.send(f'This command can only be used in <#{tournament_channel_id}>', ephemeral=True)
            return

        _queue = self.queues[ctx.channel_id]
        queue = []
        timestamp = time.monotonic()
        for p in _queue:
            if p.is_expired(timestamp):
                _queue.remove(p)
            else:
                queue.append(p.value)

        if ctx.author_id in queue:
            await ctx.send('You are already in the queue', ephemeral=True)
            return

        league = await get_current_league()
        if not league:
            await ctx.send('The league is currently closed', ephemeral=True)
            return

        player = await fetcher.gatherling_whois(discord_id=ctx.author_id)
        players = {}
        players.update({p['name']: p for p in league['players']})
        players.update({p['discord_id']: p for p in league['players']})
        if player is None or (player_name := player.get('name')) is None:
            await ctx.send("I don't know who you are.  Please [link](https://gatherling.com/auth.php) your gatherling account.", ephemeral=True)
            return
        elif player_name not in players:
            await ctx.send(f"You have not registered for [{league['name']}](https://gatherling.com/eventreport.php?event={league['id']})", ephemeral=True)
            return

        expire = time.monotonic() + TTL
        _queue.append(TTLItem(ctx.author_id, expire))

        if queue:
            potential = set()
            for lp in league['players']:
                if int(lp['discord_id']) in queue:
                    potential.add(lp)

            for m in league['matches']:
                if m['playera'] == player_name:
                    potential.remove(players[m['playerb']])
                elif m['playerb'] == player_name:
                    potential.remove(players[m['playera']])

            if potential:
                lp = potential.pop()
                await ctx.send(f"League pop between <@{lp['discord_id']}> and <@{ctx.author_id}>")
                return

        await ctx.send('You are now in queue.', ephemeral=True)

    @queue.subcommand(sub_cmd_name='leave', sub_cmd_description='Leave the queue')
    async def queue_leave(self, ctx: MtgContext) -> None:
        tournament_channel_id = configuration.get_int('mos_premodern_channel_id')
        if ctx.channel_id != tournament_channel_id:
            await ctx.send(f'This command can only be used in <#{tournament_channel_id}>', ephemeral=True)
            return

        if ctx.author_id not in self.queues[ctx.channel_id]:
            await ctx.send('You are not in the queue', ephemeral=True)
            return

        self.queues[ctx.channel_id].remove(ctx.author_id)

async def get_current_league() -> Container:
    active = await fetcher.gatherling_active_events()
    for event in active:
        if event['series'] == 'Pre-Modern Monthly League' and event['mainstruct'] == 'League':
            return event
    return None
