from discordbot import command

def test_roughly_matches():
    assert command.roughly_matches('hello', 'hello')
    assert command.roughly_matches('signup', 'Sign Up')
    assert not command.roughly_matches('elephant', 'Tuba')
