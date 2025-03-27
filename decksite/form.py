import json
from typing import Any

from werkzeug.datastructures import ImmutableMultiDict

from decksite.data import deck
from magic import decklist, legality, seasons
from magic.decklist import DecklistType
from shared.container import Container
from shared.pd_exception import InvalidDataException


class Form(Container):
    def __init__(self, form: ImmutableMultiDict) -> None:
        super().__init__()
        self.update(form.to_dict())
        self.errors: dict[str, str] = {}
        self.warnings: dict[str, str] = {}

    def validate(self) -> bool:
        self.do_validation()
        return len(self.errors) == 0

# A form that involves consuming a decklist.
class DecklistForm(Form):
    def __init__(self, form: ImmutableMultiDict, person_id: int | None, mtgo_username: str | None) -> None:
        super().__init__(form)
        if person_id is not None:
            ds = deck.recent_decks_for_person(person_id)
            self.recent_decks: list[dict[str, Any]] = []
            for d in ds:
                recent_deck = {'name': d['name'], 'main': [], 'sb': []}
                for c in d.maindeck:
                    recent_deck['main'].append('{n} {c}'.format(n=c['n'], c=c['name']))
                for c in d.sideboard:
                    recent_deck['sb'].append('{n} {c}'.format(n=c['n'], c=c['name']))
                self.recent_decks.append({'name': d['name'], 'list': json.dumps(recent_deck)})
            self.has_recent_decks = len(self.recent_decks) > 0
        if mtgo_username is not None:
            self.mtgo_username = mtgo_username
        elif not hasattr(self, 'mtgo_username'):
            self.mtgo_username = ''
        self.decklist = form.get('decklist', '').strip()
        self.deck = Container()
        self.cards: DecklistType = {}
        self.card_errors: dict[str, set[str]] = {}
        self.card_warnings: dict[str, set[str]] = {}

    def do_validation(self) -> None:
        raise NotImplementedError

    def parse_and_validate_decklist(self, check_legality: bool = True) -> None:
        if len(self.decklist) == 0:
            self.errors['decklist'] = 'Decklist is required'
        else:
            self.parse_decklist()
            if self.cards is not None:
                self.vivify_deck()
            if self.deck and check_legality:
                self.check_deck_legality()

    def parse_decklist(self) -> None:
        if self.decklist.startswith('<?xml'):
            try:
                self.cards = decklist.parse_xml(self.decklist)
            except InvalidDataException:
                self.errors['decklist'] = 'Unable to read .dek decklist. Try exporting from Magic Online as Text and pasting the result.'
        else:
            try:
                self.cards = decklist.parse(self.decklist)
            except InvalidDataException as e:
                self.errors['decklist'] = f'{str(e)}. Try exporting from Magic Online as Text and pasting the result.'

    def vivify_deck(self) -> None:
        try:
            self.deck = decklist.vivify(self.cards)
        except InvalidDataException as e:
            self.errors['decklist'] = str(e)

    def check_deck_legality(self) -> None:
        errors: dict[str, dict[str, set[str]]] = {}
        season_name = seasons.current_season_name()
        if season_name not in legality.legal_formats(self.deck, None, errors):
            self.errors['decklist'] = ' '.join(errors.get(season_name, {}).pop('Legality_General', ['Not a legal deck']))
            self.card_errors = errors.get(season_name, {})
        banned_for_bugs = {c.name for c in self.deck.all_cards() if any(b.get('bannable', False) for b in c.bugs or [])}
        playable_bugs = {c.name for c in self.deck.all_cards() if c.pd_legal and any(not b.get('bannable', False) for b in c.bugs or [])}
        if len(banned_for_bugs) > 0:
            self.errors['decklist'] = 'Deck contains cards with game-breaking bugs'
            self.card_errors['Legality_Bugs'] = banned_for_bugs
        if len(playable_bugs) > 0:
            self.warnings['decklist'] = 'Deck contains playable bugs'
            self.card_warnings['Warnings_Bugs'] = playable_bugs
