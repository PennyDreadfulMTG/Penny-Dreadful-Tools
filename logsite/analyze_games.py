import json
import re
from typing import List

def analyze_game(lines: List[str]) -> None:
    game = {'turns': [], 'mulligans': {}}
    turn = None
    turns = 0
    for line in lines:
        line = line.rstrip('\n')
        m = re.search(r' ([^ ]*) begins the game with ([^ ]*) cards in hand.', line)
        if m:
            player = m.group(1)
            if 'play' not in game:
                game['play'] = player
            game['mulligans'][player] = get_mulligans(m.group(2))
        m = re.search(r'Turn ([\d]+): ([^ ]*)', line)
        if m:
            turns += 1
            if turn is not None:
                game['turns'].append(turn)
            turn = {'number': int(m.group(1)), 'active_player': m.group(2), 'plays': {}}

        m = re.search(r'([^ ]*) (plays|casts) \[([^\]]*)]', line)
        if m:
            player = m.group(1)
            card = m.group(3)
            if player not in turn['plays']:
                turn['plays'][player] = []
            turn['plays'][player].append(card)

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
    if turn is not None:
        game['turns'].append(turn)
    game['number_of_turns'] = turns
    return game

def get_mulligans(number: str) -> int:
    nums = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7}
    return 7 - nums[number]

with open('/tmp/game.log') as f:
    lines = f.readlines()
    print(json.dumps(analyze_game(lines)))