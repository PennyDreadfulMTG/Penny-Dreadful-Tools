import json
import re
from typing import List

def analyze_game(lines: List[str]) -> None:
    game = {'mulligans': {}, 'plays': {}}    
    game_turn = 0
    player_turn = 0
    active_player = None
    for line in lines:
        line = line.rstrip('\n')
        m = re.search(r'] ([^ ]*) (.*)begins the game with ([^ ]*) cards in hand.', line)
        if m:
            player = m.group(1)
            if 'play' not in game:
                game['play'] = player
            game['mulligans'][player] = get_mulligans(m.group(3))
            game['plays'][player] = []
        m = re.search(r'Turn ([\d]+): ([^ ]*)', line)
        if m:
            game_turn += 1
            player_turn = int(m.group(1))
            active_player = m.group(2)

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

with open('/home/jesus/personal/programacion/temp/log2.txt') as f:
    lines = f.readlines()
    print(json.dumps(analyze_game(lines), sort_keys=True, indent=4))



# Tables to populate

# deck_game_played
# id, deck_id, match_id, game_number, result, mulligans
# card_played
# id, deck_game_played_id, card, turn
# one to many to: 
# id, card_played_id, related_card







def old_analyze_game(lines: List[str]) -> None:
    game = {'turns': [], 'mulligans': {}}
    plays = {}
    turn = None
    turns = 0
    turn_number = 0
    active_player = None
    for line in lines:
        line = line.rstrip('\n')
        m = re.search(r'] ([^ ]*) (.*)begins the game with ([^ ]*) cards in hand.', line)
        if m:
            player = m.group(1)
            if 'play' not in game:
                game['play'] = player
            game['mulligans'][player] = get_mulligans(m.group(3))
            plays[player] = []
        m = re.search(r'Turn ([\d]+): ([^ ]*)', line)
        if m:
            turns += 1
            if turn is not None:
                game['turns'].append(turn)
            turn_number = int(m.group(1))
            active_player = m.group(2)
            turn = {'number': turn_number, 'active_player': active_player , 'plays': {}}

        m = re.search(r'([^ ]*) (plays|casts) \[([^\]]*)]', line)
        if m:
            player = m.group(1)
            card = m.group(3)
            if player not in turn['plays']:
                turn['plays'][player] = []
            turn['plays'][player].append(card)
            plays[player].append({
                'card': card,
                'turn': turn_number,
                'active_player': active_player,
                'game_turn': turns
            })

        m = re.search(r'is being attacked by (.*)', line)
        if m:
            turn['attacks'] = re.findall(r'\[([^\]]*)]', line)[1:] # skip the date prefix

        m = re.search(r'\[([^\]]*)\] blocks \[([^\]]*)', line)
        if m:
            if 'blocks' not in turn:
                turn['blocks'] = []
            turn['blocks'].append({m.group(1): m.group(2)})


        m = re.search(r'Winner: ([^ ]*)', line)
        if m:
            game['winner'] = m.group(1)
    #if turn is not None:
    #    game['turns'].append(turn)
    game['number_of_turns'] = turns
    game['plays'] = plays
    return game
