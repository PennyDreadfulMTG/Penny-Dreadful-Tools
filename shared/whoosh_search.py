import re
from typing import Any, List, Optional, Tuple

import pygtrie
from whoosh.index import open_dir
from whoosh.query import And, FuzzyTerm, Or, Term

from magic import card, fetcher
from shared.whoosh_constants import WhooshConstants


# pylint: disable=unused-variable
class SearchResult():
    def __init__(
            self,
            exact: Optional[str],
            prefix_whole_word: List[str],
            other_prefixed: List[Any],
            fuzzy: Optional[List[Tuple[str, float]]]
    ) -> None:
        self.exact = exact
        self.prefix_whole_word = prefix_whole_word if prefix_whole_word else []
        self.other_prefixed = other_prefixed if other_prefixed else []
        self.fuzzy = prune_fuzzy_by_score(fuzzy if fuzzy else [])
        self.remove_duplicates()

    def has_match(self) -> bool:
        return bool(has(self.exact) or has(self.prefix_whole_word) or has(self.other_prefixed) or has(self.fuzzy))

    def is_ambiguous(self) -> bool:
        return bool(not has(self.exact) and (
            (len(self.prefix_whole_word) > 1) or
            ((len(self.prefix_whole_word) == 0) and (len(self.other_prefixed) > 1)) or
            (len(self.prefix_whole_word) == 0 and len(self.other_prefixed) == 0 and len(self.fuzzy) > 1)
            ))

    def get_best_match(self) -> Optional[str]:
        if not self.has_match() or self.is_ambiguous():
            return None
        if self.exact:
            return self.exact
        if has(self.prefix_whole_word):
            return self.prefix_whole_word[0]
        if has(self.other_prefixed):
            return self.other_prefixed[0]
        return self.fuzzy[0]

    def get_ambiguous_matches(self) -> List[str]:
        if not self.is_ambiguous():
            return []
        if has(self.prefix_whole_word):
            return self.prefix_whole_word
        if has(self.other_prefixed):
            return self.other_prefixed
        return self.fuzzy

    def get_all_matches(self) -> List[str]:
        if not self.has_match():
            return []
        return [r for r in ([self.exact] + self.prefix_whole_word + self.other_prefixed + self.fuzzy) if r is not None]

    def remove_duplicates(self) -> None:
        for n in [self.exact] + self.prefix_whole_word + self.other_prefixed:
            try:
                self.fuzzy.remove(n)
            except ValueError:
                pass

    def __str__(self):
        return '(exact: {e}, whole word: {r}, other prefixes: {o}, fuzzy: {f})'.format(e=self.exact, r=self.prefix_whole_word, o=self.other_prefixed, f=self.fuzzy)

    def __len__(self):
        return len(self.get_all_matches())

class WhooshSearcher():
    DIST = 2
    def __init__(self) -> None:
        self.ix = open_dir(WhooshConstants.index_dir)
        self.initialize_trie()

    def initialize_trie(self) -> None:
        self.trie = pygtrie.CharTrie()
        with self.ix.reader() as reader:
            for doc in reader.iter_docs():
                self.trie[list(WhooshConstants.normalized_analyzer(doc[1]['name']))[0].text] = doc[1]['name']

    def search(self, w) -> SearchResult:
        if not self.ix.up_to_date():
            self.initialize_trie() # if the index is not up to date, someone has added cards, so we reinitialize the trie

        # If we searched for an alias, make it the exact hit
        for alias, name in fetcher.card_aliases():
            if w == card.canonicalize(alias):
                return SearchResult(name, None, None, None)

        normalized = list(WhooshConstants.normalized_analyzer(w))[0].text

        # If we get matches by prefix, we return that
        exact, prefix_whole_word, other_prefixed = self.find_matches_by_prefix(normalized)
        if exact or len(prefix_whole_word) > 0 or len(other_prefixed) > 0:
            return SearchResult(exact, prefix_whole_word, other_prefixed, None)

        # We try fuzzy and stemmed queries
        query_normalized = fuzzy_term(normalized, self.DIST, 'name_normalized')
        query_stemmed = And([Term('name_stemmed', q.text) for q in WhooshConstants.stem_analyzer(w)])
        query_tokenized = And([fuzzy_term(q.text, self.DIST, 'name_tokenized') for q in WhooshConstants.tokenized_analyzer(w)])
        query = Or([query_normalized, query_tokenized, query_stemmed])

        with self.ix.searcher() as searcher:
            fuzzy = [(r['name'], r.score) for r in searcher.search(query, limit=40)]
        return SearchResult(exact, prefix_whole_word, other_prefixed, fuzzy)

    def find_matches_by_prefix(self, query: str) -> Tuple[Optional[str], List[str], List[str]]:
        exact = None
        prefix_as_whole_word = []
        other_prefixed = []
        if self.trie.has_key(query):
            exact = self.trie.get(query)
        if self.trie.has_subtrie(query):
            matches = self.trie.values(query)[(1 if exact else 0):]
            whole_word, subword = classify(matches, query)
            prefix_as_whole_word.extend(whole_word)
            other_prefixed.extend(subword)

        return (exact, prefix_as_whole_word, other_prefixed)

def has(elements) -> bool:
    return bool(elements and len(elements) > 0)

WordSubword = Tuple[List[str], List[str]] # pylint: disable=invalid-name

def classify(matches: List[str], word: str) -> WordSubword:
    regex = r'{w}( |,)'.format(w=word)
    acc: WordSubword = ([], []) # Name this data structure.
    for match in matches:
        if re.match(regex, match.lower()):
            acc[0].append(match)
        else:
            acc[1].append(match)
    return acc

def fuzzy_term(q, dist, field) -> Term:
    if len(q) <= 3:
        return Term(field, q)
    return FuzzyTerm(field, q, maxdist=dist, prefixlength=1)

def prune_fuzzy_by_score(fuzzy: List[Tuple[str, float]]) -> List[str]:
    if len(fuzzy) == 0:
        return []
    if len(fuzzy) == 1:
        return [fuzzy[0][0]]
    top = []
    low = fuzzy[0][1]
    for k, v in fuzzy:
        if v >= fuzzy[0][1]:
            top.append(k)
        else:
            low = v
            break
    if fuzzy[0][1] >= low * 2:
        return top
    return [f[0] for f in fuzzy]
