from manabase_solver import (DEFAULT_WEIGHTS, UnsatisfiableConstraint, card, make_deck,
                             penny_dreadful_lands, solve)
from werkzeug.datastructures import ImmutableMultiDict

from decksite.form import DecklistForm


class ManabaseForm(DecklistForm):
    def __init__(self, form: ImmutableMultiDict, person_id: int | None, mtgo_username: str | None):
        super().__init__(form, person_id, mtgo_username)
        self.output = ''

    def do_validation(self) -> None:
        self.parse_and_validate_decklist(check_legality=False)

# This is pretty much an abomination which will fail on things like hyrbid and phyrexian mana. When manabase-solver gets
# better this can get less horrible. Works only on cards using "normal" colored pips for now.
def find_manabase(form: ManabaseForm) -> str:
    cs = set()
    for ref in form.deck.maindeck:
        mb_mana_cost = ''.join(s.replace('{', '').replace('}', '') for s in ref.card.mana_cost)
        if mb_mana_cost:
            try:
                cs.add(card(mb_mana_cost))
            except Exception as e:
                return f'Something went wrong understanding your deck: {e.__class__.__name__} {e}'
    if not cs:
        return 'No constraints to satisfy'
    try:
        d = make_deck(*cs)
        r = solve(d, DEFAULT_WEIGHTS, penny_dreadful_lands)
        if r is None:
            return 'Unable to find a manabase for that deck'
        return str(r)
    except UnsatisfiableConstraint as e:
        return f'Unable to satisfy the following constraint: {e}'
    except Exception as e:
        return f'Something went wrong figuring out a manabase: {e.__class__.__name__} {e}'
