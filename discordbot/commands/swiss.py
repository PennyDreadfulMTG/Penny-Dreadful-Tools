from typing import Optional
import re

from discord.ext import commands

from discordbot.command import MtgContext
from magic import tournaments


@commands.command()
async def swiss(ctx: MtgContext, *, args: Optional[str]) -> None:
    """Display the record need to reach the elimination rounds for X players with (optionally) Y rounds of Swiss and (optionally) Top Z. 'swiss 33', 'swiss 128 7', 'swiss 12 4 4'"""
    try:
        argv = args.split()
        num_players = int(argv[0])
    except (AttributeError, IndexError, TypeError): # BAKERT what is the error for "that's not an int", test with extra spaces
        await ctx.send(f'{ctx.author.mention}: Please provide the number of players.')
    try:
        num_rounds = int(argv[1])
    except IndexError: # BAKERT same thing here
        num_rounds = tournaments.num_rounds_info(num_players, tournaments.StageType.SWISS_ROUNDS)
    try:
        num_elimination_rounds = int(argv[2])
    except (IndexError, ValueError):
        num_elimination_rounds = tournaments.num_rounds_info(num_players, tournaments.StageType.ELIMINATION_ROUNDS)
    players_in_elimination_rounds = 2 ** num_elimination_rounds
    # Math from https://www.mtgsalvation.com/forums/magic-fundamentals/magic-general/325775-making-the-cut-in-swiss-tournaments
    base = num_players / (2 ** num_rounds)
    num_players_by_losses = [0] * (num_rounds + 1)
    multiplier = 1
    total_so_far = 0
    record_required = None
    for losses in range(0, num_rounds + 1):
        wins = num_rounds - losses
        numerator = wins + 1
        denominator = losses
        if denominator > 0:
            multiplier *= (numerator / denominator)
        num_players_by_losses[losses] = base * multiplier
        if not record_required and players_in_elimination_rounds:
            total_so_far += num_players_by_losses[losses]
            if total_so_far >= players_in_elimination_rounds:
                record_required = f'{wins}–{losses}'
    s = ''
    for i, n in enumerate(num_players_by_losses):
        s += f'{round(n, 1)} players at {num_rounds - i}-{i}\n'
    if num_elimination_rounds:
        s += f'\nIt is likely that a record of {record_required} is needed to make the Top {players_in_elimination_rounds}'
    await ctx.send(s)
