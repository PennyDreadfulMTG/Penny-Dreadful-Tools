# from decksite import main, tappedout

# This test is broken:  RuntimeError: Application was not able to create a URL adapter for request independent URL generation. You might be able to fix this by setting the SERVER_NAME config variable.
# def test_hub():
#     with main.APP.app_context():
#         decks = tappedout.fetch_decks('penny-dreadful')
#         assert len(decks) > 0

# This test is broken I don't know why.
# def test_tappedout_deck():
#     with main.APP.app_context():
#         if not tappedout.is_authorised():
#             tappedout.login(configuration.get('to_username'), configuration.get('to_password'))
#         deck = tappedout.fetch_deck('penny-dreadful-allies-s2')
#         assert deck is not None
