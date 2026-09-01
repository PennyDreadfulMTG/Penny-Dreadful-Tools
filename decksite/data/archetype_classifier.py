"""LLM-assisted archetype guessing for the sort queue.

For each unreviewed, unclassified deck we build a short list of candidate archetypes from the
most card-similar reviewed decks (the same inverse-rarity similarity metric the site already
uses), then ask a small Claude model to pick the single best-fitting candidate. The guess is
written with reviewed=FALSE via archetype.assign, so it only pre-fills the queue and never
overrides a human decision; the confidence lands in deck_cache.similarity and shows in the
/admin/archetypes queue for one-click acceptance.

Candidate generation deliberately reuses deck.calculate_similar_decks, which was also used by
the previous hourly guesser. It considers every historical deck sharing any maindeck card other
than Plains, Island, Swamp, Mountain, or Forest with any deck in the run, then scores each
queued deck against that set. This is a broad database read and O(queued decks * possible
matches) Python work, but it preserves the established similarity semantics. The empty-queue
return and 100-deck limit bound normal hourly runs.

The first 20 distinct archetypes among the nearest reviewed decks, plus the broad root
archetypes, gave ~99% true-archetype shortlist recall in held-out backtests. Opus backtests over
three seasons put >=90-confidence guesses at ~99% agreement with human labels; the production
model is configurable because a cheaper model must be validated independently.

Playability and archetype card profiles are database-preaggregated, and load_decks can reuse
Redis-cached deck objects. Similarity scores are still recomputed for every nonempty run; the
new-card lookup is bounded to cards in that run. A refusal, error, or NONE OF THESE result
remains unclassified and is therefore tried again by the next hourly run.

Calls are synchronous in this first version so the existing maintenance command can apply its
results before exiting. The discounted Batch API needs a persisted batch id and a later
retrieval/reconciliation pass in case a human reviews a deck while the batch is in flight; it
is the better design if classifier volume makes that extra lifecycle worthwhile.

If no anthropic_api_key is configured the module falls back to the previous behaviour
(assign the archetype of the single most-similar reviewed deck), so deployment is safe
before a key is set.
"""
import json
import logging
from typing import Any, TypedDict, cast

import requests

from decksite.data import archetype, deck
from decksite.database import db
from magic import oracle, seasons
from magic.database import db as magic_db
from magic.models import Deck
from shared import configuration
from shared.database import sqlescape

logger = logging.getLogger(__name__)


class ArchetypeMetadata(TypedDict):
    name: str
    description: str
    lineage: list[str]
    top_cards: list[str]


Metadata = dict[int, ArchetypeMetadata]

# Seeded base roots that are always offered as fall-backs (a deck can always be "just Aggro").
BASE_ROOTS = ('Aggro', 'Combo', 'Control', 'Aggro-Combo', 'Aggro-Control',
              'Combo-Control', 'Midrange', 'Ramp')
IGNORE = ('Unclassified', 'Commander')
BASICS = ('Plains', 'Island', 'Swamp', 'Mountain', 'Forest', 'Wastes')
MAX_CANDIDATES = 20        # shortlist size before base roots; recall ~99% in backtests
TOP_CARDS = 16             # per-archetype signature cards shown to the model
MAX_ORACLE_CARDS = 20      # cap on new-card oracle text per deck (token control)

NONE_ANSWER = 'NONE OF THESE'
DEFAULT_MODEL = 'claude-haiku-4-5'

SYSTEM_PROMPT = (
    'You classify decks from Penny Dreadful, a rotating Magic: the Gathering format. Archetypes '
    'are permanent concepts: judge a deck by what it is trying to do, not raw card overlap. A '
    'single build-around card (e.g. Battle of Wits) can define a deck if the deck can find it. '
    'When several candidates fit, prefer the most specific; broad buckets (plain Aggro/Combo/'
    'Control/Midrange) are fallbacks. The player-given deck name is a hint (often the archetype '
    'or a key card) but can be a joke or wrong. For each deck you are given a short list of '
    'candidate archetypes pre-selected as most similar. Pick the single best-fitting candidate. '
    f'If none of the candidates could reasonably describe the deck, answer "{NONE_ANSWER}". Set '
    'possible_new_variant to true if the deck looks like a distinct new take that is not quite '
    'any candidate even when one fits on cards alone.'
)

OUTPUT_SCHEMA = {
    'type': 'object',
    'properties': {
        'archetype': {'type': 'string'},
        'confidence': {'type': 'integer', 'minimum': 0, 'maximum': 100},
        'possible_new_variant': {'type': 'boolean'},
        'variant_note': {'type': 'string'},
    },
    'required': ['archetype', 'confidence', 'possible_new_variant', 'variant_note'],
    'additionalProperties': False,
}


def run(limit: int = 100) -> None:
    decks, _ = deck.load_decks('NOT reviewed AND d.archetype_id IS NULL', order_by='d.created_date DESC', limit=f'LIMIT {int(limit)}')
    if not decks:
        return
    deck.calculate_similar_decks(decks)
    api_key = configuration.get_optional_str('anthropic_api_key')
    if not api_key:
        logger.warning('archetype_classifier: no anthropic_api_key configured, using nearest-deck fallback')
        _fallback(decks)
        return
    meta = _load_metadata(decks)
    new_cards = _new_cards_this_season(decks)
    model = configuration.get_optional_str('archetype_classifier_model') or DEFAULT_MODEL
    for d in decks:
        try:
            _classify_one(api_key, model, d, meta, new_cards)
        except Exception:  # one bad deck must not abort the whole run
            logger.exception('archetype_classifier: failed on deck %s', d.id)


def _classify_one(api_key: str, model: str, d: Deck, meta: Metadata, new_cards: set[str]) -> None:
    candidates = _shortlist(d, meta)
    if not candidates:
        return
    name_to_id = {name.strip().lower(): aid for aid, name in candidates}
    prompt = _deck_prompt(d, candidates, meta, new_cards)
    data = _call(api_key, model, prompt)
    if data is None:
        return
    chosen = (data.get('archetype') or '').strip()
    if chosen.upper() == NONE_ANSWER or chosen.lower() not in name_to_id:
        # Nothing fit: leave for a human. A future novelty pass can use this + possible_new_variant.
        logger.info('archetype_classifier: deck %s -> no candidate (%r, new_variant=%s)', d.id, chosen, data.get('possible_new_variant'))
        return
    archetype_id = name_to_id[chosen.lower()]
    confidence = int(data.get('confidence') or 0)
    archetype.assign(d.id, archetype_id, None, False, confidence)


def _shortlist(d: Deck, meta: Metadata) -> list[tuple[int, str]]:
    """(archetype_id, name) candidates: archetypes of the most-similar reviewed decks, plus base roots."""
    ids: list[int] = []
    seen: set[int] = set()
    for s in getattr(d, 'similar_decks', []):
        if s.reviewed and s.archetype_id is not None and s.archetype_id not in seen:
            candidate_meta = meta.get(s.archetype_id)
            if candidate_meta is not None and candidate_meta['name'] in IGNORE:
                continue
            seen.add(s.archetype_id)
            ids.append(s.archetype_id)
        if len(ids) >= MAX_CANDIDATES:
            break
    for aid in _base_root_ids():
        if aid not in seen:
            seen.add(aid)
            ids.append(aid)
    return [(aid, meta[aid]['name']) for aid in ids if aid in meta]


def _deck_prompt(d: Deck, candidates: list[tuple[int, str]], meta: Metadata, new_cards: set[str]) -> str:
    lines = [f'Player-given deck name: {d.name}', '', f'Candidate archetypes (choose one, or {NONE_ANSWER}):', '']
    for aid, _name in candidates:
        lines.append(_entry_text(meta[aid]))
    lines.append('Decklist maindeck:')
    deck_new_cards: list[str] = []
    for c in d.get('maindeck', []):
        lines.append(f"{c['n']} {c.name}")
        if c.name in new_cards and len(deck_new_cards) < MAX_ORACLE_CARDS:
            deck_new_cards.append(c.name)
    lines.append('Sideboard:')
    for c in d.get('sideboard', []):
        lines.append(f"{c['n']} {c.name}")
    if deck_new_cards:
        lines.append('')
        lines.append('Rules text for cards new this season (in case you are unfamiliar):')
        for name in deck_new_cards:
            card = oracle.cards_by_name().get(name)
            text = (card.get('oracle_text') if card else '') or ''
            lines.append(f'{name}: {text}')
    return '\n'.join(lines)


def _entry_text(m: ArchetypeMetadata) -> str:
    lines = [f"### {m['name']}"]
    if m['lineage']:
        lines.append('Family: ' + ' > '.join(m['lineage']))
    if m['description']:
        lines.append('Description: ' + m['description'])
    if m['top_cards']:
        lines.append('Most-played cards: ' + ', '.join(m['top_cards']))
    return '\n'.join(lines) + '\n'


def _call(api_key: str, model: str, prompt: str) -> dict[str, Any] | None:
    response = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
            'x-api-key': api_key,
        },
        json={
            'model': model,
            'max_tokens': 400,
            'system': SYSTEM_PROMPT,
            'output_config': {'format': {'type': 'json_schema', 'schema': OUTPUT_SCHEMA}},
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()
    if result.get('stop_reason') == 'refusal':
        return None
    text = next((b['text'] for b in result.get('content', []) if b.get('type') == 'text'), None)
    return cast(dict[str, Any], json.loads(text)) if text else None


# --- metadata -------------------------------------------------------------------------------

def _load_metadata(decks: list[Deck]) -> Metadata:
    ids = set(_base_root_ids())
    for d in decks:
        for s in getattr(d, 'similar_decks', []):
            if s.reviewed and s.archetype_id is not None:
                ids.add(s.archetype_id)
    if not ids:
        return {}
    id_list = ', '.join(str(int(i)) for i in ids)
    meta: Metadata = {}
    for row in db().select(f'SELECT id, name, description FROM archetype WHERE id IN ({id_list})'):
        meta[row['id']] = {'name': row['name'], 'description': (row['description'] or '').strip(), 'lineage': [], 'top_cards': []}
    # immediate-to-root lineage from the closure table
    lineage: dict[int, list[int]] = {}
    for row in db().select(f'SELECT descendant, ancestor, depth FROM archetype_closure WHERE descendant IN ({id_list}) AND depth > 0 ORDER BY depth DESC'):
        lineage.setdefault(row['descendant'], []).append(row['ancestor'])
    names = {row['id']: row['name'] for row in db().select('SELECT id, name FROM archetype')}
    for aid, ancestors in lineage.items():
        if aid in meta:
            meta[aid]['lineage'] = [names[a] for a in ancestors if a in names]
    _load_top_cards(meta, id_list)
    return meta


def _load_top_cards(meta: Metadata, id_list: str) -> None:
    basics = ', '.join(sqlescape(b) for b in BASICS)
    # This daily preaggregation avoids adding another deck/deck_card history scan to an hourly
    # job whose similarity pass is already deliberately broad. Use each archetype's latest
    # active season so dormant archetypes still have a useful signature.
    rows = db().select(f"""
        SELECT counts.archetype_id AS aid, counts.name AS card, counts.num_decks_maindeck AS n
        FROM _season_archetype_card_count AS counts
        INNER JOIN (
            SELECT archetype_id, MAX(season_id) AS season_id
            FROM _season_archetype_card_count
            WHERE archetype_id IN ({id_list})
            GROUP BY archetype_id
        ) AS latest ON latest.archetype_id = counts.archetype_id AND latest.season_id = counts.season_id
        WHERE counts.archetype_id IN ({id_list}) AND counts.name NOT IN ({basics})
    """)
    by_arch: dict[int, list[tuple[int, str]]] = {}
    for row in rows:
        by_arch.setdefault(row['aid'], []).append((row['n'], row['card']))
    for aid, cards in by_arch.items():
        if aid in meta:
            top = sorted(cards, reverse=True)[:TOP_CARDS]
            meta[aid]['top_cards'] = [card for _n, card in top]


def _new_cards_this_season(decks: list[Deck]) -> set[str]:
    """Cards in this run whose first printing was released after the last rotation.

    Restricting the printing query to cards in the queued decks avoids scanning deck history
    just to decide which small number of cards need oracle text in the prompt.
    """
    try:
        cutoff = int(seasons.last_rotation().timestamp())
    except Exception:
        return set()
    names_by_id: dict[int, str] = {}
    for d in decks:
        for ref in d.get('maindeck', []):
            card = oracle.cards_by_name().get(ref.name)
            if card is not None:
                names_by_id[card.id] = card.name
    if not names_by_id:
        return set()
    placeholders = ', '.join(['%s'] * len(names_by_id))
    rows = magic_db().select(f"""
        SELECT p.card_id, MIN(s.released_at) AS released_at
        FROM printing AS p
        INNER JOIN `set` AS s ON s.id = p.set_id
        WHERE p.card_id IN ({placeholders})
        GROUP BY p.card_id
        HAVING released_at >= %s
    """, [*names_by_id, cutoff])
    return {names_by_id[row['card_id']] for row in rows}


_BASE_ROOT_IDS: list[int] = []

def _base_root_ids() -> list[int]:
    if not _BASE_ROOT_IDS:
        names = ', '.join(sqlescape(n) for n in BASE_ROOTS)
        _BASE_ROOT_IDS.extend(r['id'] for r in db().select(f'SELECT id FROM archetype WHERE name IN ({names})'))
    return _BASE_ROOT_IDS


# --- fallback (no API key) ------------------------------------------------------------------

def _fallback(decks: list[Deck]) -> None:
    for d in decks:
        for s in getattr(d, 'similar_decks', []):
            if s.reviewed and s.archetype_id is not None:
                sim = int(100 * deck.similarity_score(d, s))
                if d.archetype_id != s.archetype_id:
                    archetype.assign(d.id, s.archetype_id, None, False, sim)
                break
