# type: ignore

import glob
import os
import re
import shutil

from shared import fetch_tools
from shared.pd_exception import InvalidDataException

from . import APP
from .data import game, match, tournament

REGEX_GAME_HEADER = r'== Game \d \((?P<id>\d+)\) =='
REGEX_SWITCHEROO = r'!! Warning, unexpected game 3 !!'
REGEX_GATHERLING = r'\[Gatherling\] Event=(.*)'
REGEX_ROUND = r'\[Gatherling\] Round=(.*)'


def load_from_file() -> None:
    """ "Imports a log from an on-disk file"""
    files = glob.glob('import/queue/*.txt')
    for fname in files:
        match_id = int(os.path.basename(fname).split('.')[0])
        if match.get_match(match_id) is None:
            with open(fname) as fhandle:
                lines = fhandle.readlines()
                import_log(lines, match_id)
            shutil.move(fname, f'import/processed/{match_id}.txt')
            return


def import_from_pdbot(match_id: int) -> None:
    url = f'https://pdbot.pennydreadfulmagic.com/logs/{match_id}'
    lines = fetch_tools.fetch(url).split('\n')
    import_log(lines, match_id)


def import_log(lines: list[str], match_id: int) -> match.Match:
    """Processes a log"""
    lines = [line.strip('\r\n') for line in lines]
    APP.logger.info(f'importing {match_id}')
    try:
        local = import_header(lines, match_id)
    except IndexError as e:
        raise InvalidDataException from e
    if local.has_unexpected_third_game is None:
        local.has_unexpected_third_game = False
    lines = lines[4:]
    while lines[0] != '':
        lines = lines[1:]
    game_id = 0
    game_lines: list[str] = []
    for line in lines:
        m = re.match(REGEX_GAME_HEADER, line)
        gm = re.match(REGEX_GATHERLING, line)
        gr = re.match(REGEX_ROUND, line)
        if m:
            new_id = int(m.group('id'))
            if game_id == 0:
                game_id = new_id
            elif new_id != game_id:
                game.insert_game(game_id, match_id, '\n'.join(game_lines))
                game_id = new_id
                game_lines = []
        elif re.match(REGEX_SWITCHEROO, line):
            local.has_unexpected_third_game = True
            game_lines.append(line)
        elif gm:
            tname = gm.group(1)
            APP.logger.info(f'Gatherling Event: {tname}')
            process_tourney_info(local, tname=tname)
            game_lines.append(line)
        elif gr:
            roundnum = gr.group(1)
            APP.logger.info(f'Gatherling Round: {roundnum}')
            process_tourney_info(local, roundnum=roundnum)
            game_lines.append(line)
        else:
            game_lines.append(line)
    game.insert_game(game_id, match_id, '\n'.join(game_lines))
    return local


def import_header(lines: list[str], match_id: int) -> match.Match:
    local = match.get_match(match_id)
    if local is None:
        format_name = lines[0]
        comment = lines[1]
        modules = [mod.strip() for mod in lines[2].split(',')]
        players = [player.strip() for player in lines[3].split(',')]
        local = match.create_match(match_id, format_name, comment, modules, players)
    return local


def process_tourney_info(local: match.Match, tname: str | None = None, roundnum: str | None = None) -> None:
    if tname:
        tourney = tournament.get_tournament(tname)
        if tourney is None:
            tourney = tournament.create_tournament(tname)
        local.is_tournament = True
        tournament.create_tournament_info(local.id, tourney.id)
    tourney_info = local.tournament
    if tourney_info and roundnum:
        tourney_info.round_num = roundnum


def reimport(local: match.Match) -> None:
    for lgame in local.games:
        if local.has_unexpected_third_game is None and re.match(REGEX_SWITCHEROO, lgame.log):
            local.has_unexpected_third_game = True
    if local.has_unexpected_third_game is None:
        local.has_unexpected_third_game = False
    tourney = re.search(REGEX_GATHERLING, local.games[0].log)
    local.is_tournament = tourney is not None
    if tourney:
        process_tourney_info(local, tourney.group(1))
    match.db.commit()
