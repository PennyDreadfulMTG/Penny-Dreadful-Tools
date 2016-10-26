from decksite import main, tappedout
from magic import configuration

def test_hub():
    with main.APP.app_context():
        decks = tappedout.fetch_decks("penny-dreadful")
        assert len(decks) > 0

def test_deck():
    with main.APP.app_context():
        if not tappedout.is_authorised():
            tappedout.login(configuration.get('to_username'), configuration.get('to_password'))
        deck = tappedout.fetch_deck("penny-dreadful-allies-s2")
        assert deck is not None
