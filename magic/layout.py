from dataclasses import dataclass
from typing import List, Optional

from github.GithubException import GithubException

from shared import repo


@dataclass
class Layout:
    playable: bool = True
    has_two_names: bool = False
    uses_two_names: bool = False
    has_single_back: bool = False
    has_meld_back: bool = False
    has_two_mana_costs: bool = False
    sums_cmc: bool = False
    real_card_name: bool = True
    # Exclude art_series because they have the same name as real cards and that breaks things.
    # Exclude token because named tokens like "Ajani's Pridemate" and "Storm Crow" conflict with the cards with the same name. See #6156.
    uses_canonical_namespace: bool = True

    @property
    def has_two_faces(self) -> bool:
        return self.has_single_back or self.has_meld_back


# Adding a layout here is very nearly almost the only thing you have to do when a new layout comes into existence
# (assuming it doesn't come with a bunch of new behavior that needs to be accounted for).
# The exceptions are:
# (1) modo_bugs.fetcher.search_scryfall.get_frontside which does not have access to the magic module and explicitly
# lists layouts that are the result of the logic found in magic.fetcher.search_scryfall.get_frontside (two faces but
# not two names and not meld).
# (2) If you need the weird "wait until we have all the card details" behavior of a meld card when building cards db in
# multiverse.
LAYOUTS: dict[str, Layout] = {
    'adventure': Layout(has_two_names=True, has_two_mana_costs=True),
    'art_series': Layout(playable=False, uses_canonical_namespace=False),
    'augment': Layout(playable=False),
    'class': Layout(),
    'double_faced_token': Layout(playable=False, has_two_names=True, has_single_back=True, uses_canonical_namespace=False),
    'emblem': Layout(playable=False),
    'flip': Layout(has_two_names=True),
    'host': Layout(playable=False),
    'leveler': Layout(),
    'meld': Layout(has_two_names=True, has_meld_back=True),
    'modal_dfc': Layout(has_two_names=True, has_single_back=True, has_two_mana_costs=True),
    'mutate': Layout(),
    'normal': Layout(),
    'planar': Layout(playable=False),
    'prototype': Layout(),
    # We don't quite tell the truth about 'reversible_card'. These cards DO have canonical namespace names.
    # But including them alongside their identically-named non-reversible originals causes duplicates to get added to the db which breaks things.
    # We may need to do better here if a layout:reversible_card is ever released that doesn't already exist in another playable form.
    'reversible_card': Layout(has_single_back=True, uses_canonical_namespace=False),
    'saga': Layout(),
    'scheme': Layout(playable=False),
    'split': Layout(has_two_names=True, uses_two_names=True, sums_cmc=True, has_two_mana_costs=True),
    'token': Layout(playable=False, uses_canonical_namespace=False),
    'transform': Layout(has_two_names=True, has_single_back=True),
    'vanguard': Layout(playable=False),
}

def all_layouts() -> List[str]:
    return list(LAYOUTS.keys())

def playable_layouts() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.playable]

def has_two_names() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.has_two_names]

def uses_two_names() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.uses_two_names]

def has_single_back() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.has_single_back]

def has_meld_back() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.has_meld_back]

def has_two_faces() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.has_two_faces]

def sums_cmc() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.sums_cmc]

def has_two_mana_costs() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.has_two_mana_costs]

def uses_canonical_namespace() -> List[str]:
    return [name for name, props in LAYOUTS.items() if props.uses_canonical_namespace]

def is_playable_layout(layout: str) -> bool:
    lo = LAYOUTS.get(layout)
    if lo is not None:
        return lo.playable
    report_missing_layout(layout)
    return False

def report_missing_layout(layout: Optional[str]) -> None:
    cache_key = 'missing_layout_logged'
    if not hasattr(report_missing_layout, cache_key):  # A little hack to prevent swamping github – see https://stackoverflow.com/a/422198/375262
        try:
            warning = f'Did not recognize layout `{layout}` – need to add it'
            print(warning)
            repo.create_issue(warning, 'multiverse', 'multiverse', 'PennyDreadfulMTG/perf-reports')
        except GithubException:
            pass  # We tried. Not gonna break the world because we couldn't log it.
        setattr(report_missing_layout, cache_key, [])  # The other half of the hack.
