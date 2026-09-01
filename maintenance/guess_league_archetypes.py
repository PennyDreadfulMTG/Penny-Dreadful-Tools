"""Deprecated: superseded by maintenance/classify_archetypes.py, which guesses archetypes with
an LLM and falls back to nearest-similar-deck when no anthropic_api_key is configured. The
HOURLY flag has been removed so only the new job runs in the hourly sweep; run() is kept as a
delegating alias for anything that invokes it directly."""
from decksite.data import archetype_classifier


def run() -> None:
    archetype_classifier.run()
