from decksite.database import db
import re
from typing import Any, Dict, List, Optional
from shared import fetch_tools
from shared.fetch_tools import FetchException

def analyze_game(lines: List[str], players: List[str]) -> Dict[Any, Any]:
    game = {'mulligans': {}, 'plays': {}}
    for player in players:
        game['mulligans'][player] = 0
        game['plays'][player] = []
    game_turn = 0
    player_turn = 1
    active_player = None
    for line in lines:
        line = line.rstrip('\n')

        # [07:56:45] Neiburu chooses to play first.
        m = re.search(r'] ([^ ]*) chooses to play ([^.]*).', line)
        if m:
            player = m.group(1)
            position = m.group(2)
            if position == 'first':
                game['on_the_play'] = player
            elif player == players[0]:
                game['on_the_play'] = players[1]
            else:
                game['on_the_play'] = players[0]

        # Old mulligan format:
        # Togalustir mulligans to 6 cards.
        # Inzectohawk keeps this hand.
        # Togalustir mulligans to 5 cards.
        # Togalustir keeps this hand.
        m = re.search(r'([^ ]*) mulligans to (\d) cards.', line)
        if m:
            player = m.group(1)
            if 'on_the_play' not in game:
                game['on_the_play'] = player
            game['mulligans'][player] = 7 - int(m.group(2))

        # New mulligan format: 
        # [03:31:50] joeknows88 begins the game with seven cards in hand.        
        m = re.search(r'] ([^ ]*) (.*)begins the game with ([^ ]*) cards in hand.', line)
        if m:
            player = m.group(1)
            if 'on_the_play' not in game:
                game['on_the_play'] = player
            game['mulligans'][player] = get_mulligans(m.group(3))

        # Turn 1: ezekiele.
        m = re.search(r'Turn ([\d]+): ([^ ]*)\.', line)
        if m:
            game_turn += 1            
            player_turn = int(m.group(1))
            active_player = m.group(2)

        # Fix to avoid old log formats where the first Turn 1 was missing
        # Dakmor92 skips their draw step.
        m = re.search(r'([^ ]*) skips their draw step', line)
        if m and game_turn == 0:
            game_turn = 1
            active_player = m.group(1)

        # [00:00:20] LudwigFrito casts [Tyrant's Scorn] targeting [Drannith Healer] (Destroy target creature with converted mana cost 3 or less.).
        # [23:58:57] Rydyell casts [Casualties of War] targeting [Selesnya Signet], [Najeela, the Blade-Blossom], [Pandemonium], and [Plains].
        # Not interested in: [00:00:07] LudwigFrito casts [Agonizing Remorse] targeting Rydyell.
        m = re.search(r'([^ ]*) (plays|casts) \[([^\]]*)](?: targeting (\[.*))?', line)
        if m:
            player = m.group(1)
            card = m.group(3)
            card_play = {
                'card': card,
                'player_turn': player_turn,
                'active_player': active_player,
                'game_turn': game_turn
            }
            if m.group(4) is not None:
                targets = re.findall(r'\[([^\]]*)\]', m.group(4))
                card_play['targets'] = targets
            game['plays'][player].append(card_play)

        # Public tutors

        m = re.search(r'Winner: ([^ ]*)', line)
        if m:
            game['winner'] = m.group(1)
    game['number_of_turns'] = game_turn
    return game

def get_mulligans(number: str) -> int:
    nums = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7}
    return 7 - nums[number]

def get_batch_of_matches(size: int = 10) -> List[Dict[str, int]]:
    sql = """
        SELECT 
            a.id, a.mtgo_id 
        FROM 
            `match` a 
        LEFT JOIN 
            deck_game_played b 
        ON 
            a.id=b.match_id 
        WHERE 
                a.mtgo_id IS NOT NULL 
            AND 
                b.id IS NULL 
        LIMIT %s;
    """
    return db().select(sql, [size])

def get_deck_id_and_players(match_id: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT 
            deck_id, mtgo_username 
        FROM 
            deck_match a, deck b, person c 
        WHERE 
                match_id=%s 
            AND 
                a.deck_id=b.id 
            AND 
                b.person_id=c.id;
    """
    return db().select(sql, [match_id])

def get_match_data(mtgo_id: int) -> Optional[Dict[str, str]]:
    match_data = None
    try:
        match_data = fetch_tools.fetch_json(f'https://logs.pennydreadfulmagic.com/api/match/{mtgo_id}')        
    except FetchException:
        print(f'WARNING: Couldn\'t fetch match_data for {mtgo_id}')
    if match_data is not None and 'games' in match_data:
        return match_data
    return None

def get_game(url: str) -> Optional[Dict[str, str]]:
    game = None
    try:
        game = fetch_tools.fetch_json(url)
    except FetchException:
        print(f'WARNING: Couldn\'t fetch game:  {url}')
    return game


def analyze_games(match: Dict[str, int]) -> None:
    match_data = get_match_data(match['mtgo_id'])
    if match_data is None:
        return
    games = match_data['games']
    game_number = 1
    for game in games:
        game_data = get_game(game['uri'])
        if game_data is not None:
            analysis = analyze_game(game_data['log'].splitlines(), match_data['players'])
            print(analysis)
            decks_and_players = get_deck_id_and_players(match['id'])
            new_ids = insert_deck_game_played(match['id'], game_number, decks_and_players, analysis)
            print(new_ids)
            insert_plays(analysis, new_ids)
        game_number += 1

def insert_deck_game_played(match_id: int, game_number: int, decks_and_players: List[Dict[str, Any]], analysis: Dict[Any, Any]) -> Dict[str,int]:
# {'mulligans': {'BigM': 1, 'Zchinque': 0}, 
# 'plays': {'BigM': [{'card': 'Mystic Monastery', 'player_turn': 1, 'active_player': 'BigM.', 'game_turn': 1}, {'card': 'Island', 'player_turn': 2, 'active_player': 'BigM.', 'game_turn': 3}, {'card': 'Curious Homunculus', 'player_turn': 2, 'active_player': 'BigM.', 'game_turn': 3}, {'card': 'Stormchaser Mage', 'player_turn': 3, 'active_player': 'BigM.', 'game_turn': 5}, {'card': 'Island', 'player_turn': 3, 'active_player': 'BigM.', 'game_turn': 5}, {'card': 'Obsessive Search', 'player_turn': 3, 'active_player': 'BigM.', 'game_turn': 5}, {'card': 'Mountain', 'player_turn': 4, 'active_player': 'BigM.', 'game_turn': 7}, {'card': 'Crumbling Necropolis', 'player_turn': 5, 'active_player': 'BigM.', 'game_turn': 9}], 'Zchinque': [{'card': 'Swamp', 'player_turn': 0, 'active_player': None, 'game_turn': 0}, {'card': 'Swamp', 'player_turn': 2, 'active_player': 'Zchinque.', 'game_turn': 2}, {'card': 'Mesmeric Fiend', 'player_turn': 2, 'active_player': 'Zchinque.', 'game_turn': 2}, {'card': 'Swamp', 'player_turn': 3, 'active_player': 'Zchinque.', 'game_turn': 4}, {'card': 'Carrier Thrall', 'player_turn': 3, 'active_player': 'Zchinque.', 'game_turn': 4}, {'card': 'Sultai Emissary', 'player_turn': 4, 'active_player': 'Zchinque.', 'game_turn': 6}, {'card': 'Dark Prophecy', 'player_turn': 5, 'active_player': 'Zchinque.', 'game_turn': 8}, {'card': 'Bloodthrone Vampire', 'player_turn': 6, 'active_player': 'Zchinque.', 'game_turn': 10}]}, 
# 'on_the_play': 'BigM', 'winner': 'Zchinque', 'number_of_turns': 11}
    sql = """
        INSERT INTO deck_game_played (deck_id, match_id, game_number, result, mulligans, play)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    ids_by_player = {}
    try:
        for deck_and_player in decks_and_players:
            player = deck_and_player['mtgo_username']
            result = None
            if 'winner' in analysis:
                result = 1 if player == analysis['winner'] else -1
            mulligans = None
            if 'mulligans' in analysis:
                mulligans = analysis['mulligans'][player]
            play = None
            if 'on_the_play' in analysis:
                play = 1 if player == analysis['on_the_play'] else 0
            deck_game_played_id = db().insert(sql, [deck_and_player['deck_id'], match_id, game_number, result, mulligans, play])
            ids_by_player[player] = deck_game_played_id
        return ids_by_player
    except Exception as e:
        print('Exception found', e)
        return ids_by_player

def insert_plays(analysis: Dict[Any, Any], ids_by_player: Dict[str,int]) -> None:
    sql = """
        INSERT INTO card_played (deck_game_played_id, card, game_turn, player_turn, active_player)
        VALUES (%s, %s, %s, %s, %s);
    """
    for player, deck_game_played_id in ids_by_player.items():
        for card_play in analysis['plays'][player]:
            active_player = 1 if player == card_play['active_player'] else 0
            new_id = db().insert(sql, [deck_game_played_id, card_play['card'], card_play['game_turn'], card_play['player_turn'], active_player])
            if 'targets' in card_play:
                insert_targets_for_card(card_play, new_id)

def insert_targets_for_card(card_play: Dict[Any, Any], new_id: int) -> None:
    sql = """
        INSERT INTO card_played_affects (card_played_id, card)
        VALUES (%s, %s);
    """
    for target in card_play['targets']:
        db().insert(sql, [new_id, target])

def ad_hoc() -> None:
    matches = get_batch_of_matches(1)
    if len(matches) > 0:
        print("Analyzing log games for these matches/mtgo_id: ")
        print([(x['id'],x['mtgo_id']) for x in matches])

    for match in matches:
        analyze_games(match)

# Tables to populate

# deck_game_played
# id, deck_id, match_id, game_number, result, mulligans, play
# card_played
# id, deck_game_played_id, card, turn
# one to many to cards_affected: 
# id, card_played_id, affected_card
