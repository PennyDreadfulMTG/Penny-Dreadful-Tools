from .monolith_checker import MonolithChecker

def register(linter):
    """Required method to auto register this checker.

    Args:
        linter: Main interface object for Pylint plugins.
    """
    linter.register_checker(MonolithChecker(linter))

ACCEPTABLE_IMPORTS = {
    'decksite': ('decksite', 'magic', 'shared', 'shared_web'),
    'discordbot': ('discordbot', 'magic', 'shared'),
    'logsite': ('logsite', 'shared', 'shared_web'),
    'magic': ('magic', 'shared'),
    'maintenance': ('decksite', 'magic', 'maintenance', 'shared', 'shared_web'),
    'price_grabber': ('price_grabber', 'magic', 'shared'),
    'pylint_monolith': ('pylint_monolith'),
    'rotation_script': ('rotation_script', 'price_grabber', 'magic', 'shared'),
    'shared': ('shared'),
    'shared_web': ('shared_web', 'shared'),

    'dev': ('magic'),
    'generate_readme': ('discordbot'),
    'run': ('discordbot', 'decksite', 'price_grabber', 'rotation_script', 'magic'),
}
