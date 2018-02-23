import re

import pygtrie
from whoosh.index import open_dir
from whoosh.query import And, FuzzyTerm, Or, Term

from magic import card, fetcher
from shared.whoosh_constants import WhooshConstants


# pylint: disable=unused-variable
class SearchResult():
    def __init__(self, exact, prefix_whole_word, other_prefixed, fuzzy):
        self.exact = exact
        self.prefix_whole_word = prefix_whole_word if prefix_whole_word else []
        self.other_prefixed = other_prefixed if other_prefixed else []
        self.fuzzy = fuzzy if fuzzy else []
        self.prune_fuzzy_by_score()
        self.remove_duplicates()

    def has_match(self):
        return bool(has(self.exact) or has(self.prefix_whole_word) or has(self.other_prefixed) or has(self.fuzzy))

    def is_ambiguous(self):
        return bool(not has(self.exact) and (
            (len(self.prefix_whole_word) > 1) or
            ((len(self.prefix_whole_word) == 0) and (len(self.other_prefixed) > 1)) or
            (len(self.prefix_whole_word) == 0 and len(self.other_prefixed) == 0 and len(self.fuzzy) > 1)
            ))

    def get_best_match(self):
        if not self.has_match() or self.is_ambiguous():
            return None
        if self.exact:
            return self.exact
        if has(self.prefix_whole_word):
            return self.prefix_whole_word[0]
        if has(self.other_prefixed):
            return self.other_prefixed[0]
        return self.fuzzy[0]

    def get_ambiguous_matches(self):
        if not self.is_ambiguous():
            return None
        if has(self.prefix_whole_word):
            return self.prefix_whole_word
        if has(self.other_prefixed):
            return self.other_prefixed
        return self.fuzzy

    def get_all_matches(self):
        if not self.has_match():
            return []
        return [r for r in ([self.exact] + self.prefix_whole_word + self.other_prefixed + self.fuzzy) if r is not None]

    def prune_fuzzy_by_score(self):
        if len(self.fuzzy) == 0:
            return
        if len(self.fuzzy) == 1:
            self.fuzzy = [self.fuzzy[0][0]]
            return
        if self.fuzzy[0][1] >= self.fuzzy[1][1] * 2:
            self.fuzzy = [self.fuzzy[0][0]]
            return
        self.fuzzy = [f[0] for f in self.fuzzy]

    def remove_duplicates(self):
        for n in [self.exact] + self.prefix_whole_word + self.other_prefixed:
            try:
                self.fuzzy.remove(n)
            except ValueError:
                pass

    def __str__(self):
        return "(exact: {e}, whole word: {r}, other prefixes: {o}, fuzzy: {f})".format(e=self.exact, r=self.prefix_whole_word, o=self.other_prefixed, f=self.fuzzy)

class WhooshSearcher():
    DIST = 2
    def __init__(self):
        self.ix = open_dir(WhooshConstants.index_dir)
        self.initialize_trie()

    def initialize_trie(self):
        self.trie = pygtrie.CharTrie()
        with self.ix.reader() as reader:
            for doc in reader.iter_docs():
                self.trie[list(WhooshConstants.normalized_analyzer(doc[1]['name']))[0].text] = doc[1]['name']

    def search(self, w):
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
        query_normalized = fuzzy_term(normalized, self.DIST, "name_normalized")
        query_stemmed = And([Term('name_stemmed', q.text) for q in WhooshConstants.stem_analyzer(w)])
        query_tokenized = And([fuzzy_term(q.text, self.DIST, "name_tokenized") for q in WhooshConstants.tokenized_analyzer(w)])
        query = Or([query_normalized, query_tokenized, query_stemmed])

        with self.ix.searcher() as searcher:
            fuzzy = [(r['name'], r.score) for r in searcher.search(query, limit=40)]
        return SearchResult(exact, prefix_whole_word, other_prefixed, fuzzy)

    def find_matches_by_prefix(self, query):
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

def has(elements):
    return bool(elements and len(elements) > 0)

def classify(matches, word):
    regex = r"{w}( |,)".format(w=word)
    acc = ([], [])
    for match in matches:
        if re.match(regex, match.lower()):
            acc[0].append(match)
        else:
            acc[1].append(match)
    return acc

def fuzzy_term(q, dist, field):
    if len(q) <= 3:
        return Term(field, q)
    return FuzzyTerm(field, q, maxdist=dist, prefixlength=1)
