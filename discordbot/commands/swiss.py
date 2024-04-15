import math

from interactions import Client
from interactions.models import Extension, OptionType, slash_command, slash_option

from discordbot.command import MtgInteractionContext, migrate_to_slash_command
from magic import tournaments


class Swiss(Extension):
    def __init__(self, bot: Client) -> None:
        self.bot = bot
        super().__init__()

    @slash_command('swiss')
    @slash_option(
        name='num_players',
        description='number of players in the event',
        opt_type=OptionType.INTEGER,
        required=True)
    @slash_option(
        name='num_rounds',
        description='number of rounds of Swiss',
        opt_type=OptionType.INTEGER,
        required=False)
    @slash_option(
        name='top_n',
        description='number of players who make it to the elimination round (ie: Top N)',
        opt_type=OptionType.INTEGER,
        required=False)
    async def swiss(self, ctx: MtgInteractionContext, num_players: int, num_rounds: int | None = None, top_n: int | None = None) -> None:
        """Display the record need to reach the elimination rounds for a given tournament"""
        if not num_players:
            await ctx.send(f'{ctx.author.mention}: Please provide the number of players.')
            return
        if not num_rounds:
            num_rounds = tournaments.num_rounds_info(num_players, tournaments.StageType.SWISS_ROUNDS)
        if top_n:
            num_elimination_rounds = math.ceil(math.log2(top_n))
        else:
            num_elimination_rounds = tournaments.num_rounds_info(num_players, tournaments.StageType.ELIMINATION_ROUNDS)
            top_n = 2 ** num_elimination_rounds
        s = f'For {num_players} players and {num_rounds} rounds of swiss:\n'
        num_players_by_losses, record_required = swisscalc(num_players, num_rounds, num_elimination_rounds)
        players_in_top_n = 0
        players_who_dont_miss = None  # number of players with the worst record that still makes top 8 who make top 8
        for i, n in enumerate(num_players_by_losses):
            s += f'{round(n, 1)} players at {num_rounds - i}-{i}\n'
            players_in_top_n += n
            if top_n is not None:
                if players_in_top_n >= top_n and players_who_dont_miss is None:
                    players_who_dont_miss = n + top_n - players_in_top_n
        if players_who_dont_miss is None:
            players_who_dont_miss = num_players

        if record_required and top_n:
            if abs(players_who_dont_miss - int(players_who_dont_miss)) < 0.000001:  # if it's an integer number of players
                people_person = 'people' if round(players_who_dont_miss) != 1 else 'person'
                s += f'\nIt is likely that {round(players_who_dont_miss)} {people_person} with a record of {record_required} will make the Top {top_n}'
            else:
                s += f'\nIt is likely that {int(players_who_dont_miss)} or {int(players_who_dont_miss) + 1} ({round(players_who_dont_miss, 1)}) people with a record of {record_required} will make the Top {top_n}'
        await ctx.send(s)

    m_swiss = migrate_to_slash_command(swiss)

def swisscalc(num_players: int, num_rounds: int, num_elimination_rounds: int) -> tuple[list[int], str | None]:
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

def setup(bot: Client) -> None:
    Swiss(bot)
