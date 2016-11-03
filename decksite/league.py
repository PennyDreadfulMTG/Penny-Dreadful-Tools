import json

from munch import Munch

from magic import legality
from shared.pd_exception import InvalidDataException

from decksite.data import deck
from decksite.scrapers import decklist

class Form(Munch):
    def __init__(self, form):
        super().__init__()
        form = form.to_dict()
        self.update(form)
        self.errors = {}

    def validate(self):
        self.do_validation()
        return len(self.errors) == 0

# pylint: disable=attribute-defined-outside-init
class SignUpForm(Form):
    def do_validation(self):
        if len(self.mtgo_username) == 0:
            self.errors['mtgo_username'] = "MTGO Username is required"
        if len(self.name) == 0:
            self.errors['name'] = 'Deck Name is required'
        else:
            self.source = 'League'
            self.identifier = json.dumps([self.mtgo_username, self.name, '2-2'])
            self.url = 'http://pennydreadfulmagic.com/'
            if deck.get_deck_id(deck.get_source_id(self.source), self.identifier):
                self.errors['name'] = 'You have already entered the league this season with a deck called {name}'.format(name=self.name)
        if len(self.decklist) == 0:
            self.errors['decklist'] = 'Decklist is required'
        else:
            try:
                d = decklist.parse_and_vivify(self.decklist)
                if 'Penny Dreadful' not in legality.legal_formats(d):
                    self.errors['decklist'] = 'Deck is not legal in Penny Dreadful'
            except InvalidDataException:
                self.errors['decklist'] = 'Unable to parse decklist. Try exporting from MTGO as Text and pasting the result.'

def signup(form):
    params = form
    params['cards'] = decklist.parse(form.decklist)
    return deck.add_deck(params)
