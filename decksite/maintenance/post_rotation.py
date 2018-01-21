from magic import multiverse
from . import reprime_cache

def ad_hoc():
    multiverse.init() # New Cards?
    multiverse.set_legal_cards() # PD current list
    multiverse.update_pd_legality() # PD previous lists
    reprime_cache.ad_hoc() # Update deck legalities
