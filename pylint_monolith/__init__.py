from .monolith_checker import MonolithChecker
from .l18n_check import TranslationStringConstantsChecker

def register(linter):
    """Required method to auto register this checker.

    Args:
        linter: Main interface object for Pylint plugins.
    """
    linter.register_checker(MonolithChecker(linter))
    linter.register_checker(TranslationStringConstantsChecker(linter))
