import math
from typing import List, Optional, Tuple

from discord.ext import commands

from discordbot.command import MtgContext
from magic import tournaments


@commands.command()
async def swiss(ctx: MtgContext, num_players: Optional[int], num_rounds: Optional[int], top_n: Optional[int]) -> None:
    """Display the record need to reach the elimination rounds for X players with (optionally) Y rounds of Swiss and (optionally) Top Z. 'swiss 33', 'swiss 128 7', 'swiss 12 4 4'"""
    if not num_players:
        return await ctx.send(f'{ctx.author.mention}: Please provide the number of players.')
    if not num_rounds:
        num_rounds = tournaments.num_rounds_info(num_players, tournaments.StageType.SWISS_ROUNDS)
    if top_n:
        num_elimination_rounds = math.ceil(math.log2(top_n))
    if not top_n:
        num_elimination_rounds = tournaments.num_rounds_info(num_players, tournaments.StageType.ELIMINATION_ROUNDS)
        top_n = 2 ** num_elimination_rounds
    s = ''
    num_players_by_losses, record_required = swisscalc(num_players, num_rounds, num_elimination_rounds)
    players_in_top_n = 0
    players_who_dont_miss = None  # number of players with the worst record that still makes top 8 who make top 8
    for i, n in enumerate(num_players_by_losses):
        s += f'{round(n, 1)} players at {num_rounds - i}-{i}\n'
        players_in_top_n += n
        if top_n is not None:
            if players_in_top_n > top_n and players_who_dont_miss is None:
                players_who_dont_miss = n + top_n - players_in_top_n
    if players_who_dont_miss is None:
        players_who_dont_miss = num_players

    if record_required and top_n:
        if abs(players_who_dont_miss - int(players_who_dont_miss)) < 0.000001:  # if it's an integer number of players
            people_person = "people" if round(players_who_dont_miss) != 1 else "person"
            s += f'\nIt is likely that {round(players_who_dont_miss)} {people_person} with a record of {record_required} will make the Top {top_n}'
        else:
            s += f'\nIt is likely that {int(players_who_dont_miss)} or {int(players_who_dont_miss) + 1} ({round(players_who_dont_miss, 1)}) people with a record of {record_required} will make the Top {top_n}'
    await ctx.send(s)

def swisscalc(num_players: int, num_rounds: int, num_elimination_rounds: int) -> Tuple[List[int], Optional[str]]:
    players_in_elimination_rounds = 2 ** num_elimination_rounds
    # Math from https://www.mtgsalvation.com/forums/magic-fundamentals/magic-general/325775-making-the-cut-in-swiss-tournaments
    base = num_players / (2 ** num_rounds)
    num_players_by_losses = [0] * (num_rounds + 1)
    multiplier = 1.0
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
    return (num_players_by_losses, record_required)
