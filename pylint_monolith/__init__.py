from pylint.lint import PyLinter
from .l18n_check import TranslationStringConstantsChecker
from .monolith_checker import MonolithChecker


def register(linter: PyLinter) -> None:
    """Required method to auto register this checker.

    Args:
        linter: Main interface object for Pylint plugins.
    """
    linter.register_checker(MonolithChecker(linter))
    linter.register_checker(TranslationStringConstantsChecker(linter))
