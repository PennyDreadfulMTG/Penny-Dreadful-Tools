def add_deck(params):
    pass

class Deck(dict):
    def __init__(self, params):
        super().__init__()
        for k in params.keys():
            self[k] = params[k]


class Decklist():
    pass
