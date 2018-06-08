from .monolith_checker import MonolithChecker


def register(linter):
    """Required method to auto register this checker.

    Args:
        linter: Main interface object for Pylint plugins.
    """
    linter.register_checker(MonolithChecker(linter))
