import itertools
from whoosh.index import open_dir
from whoosh.query import And, FuzzyTerm, Or, Term

from shared.whoosh_constants import WhooshConstants
from shared.container import Container


class WhooshSearcher():
    DIST = 2
    def __init__(self):
        self.ix = open_dir(WhooshConstants.index_dir)

    def search(self, w):
        normalized = list(WhooshConstants.normalized_analyzer(w))[0].text
        query_normalized = fuzzy_term(normalized, self.DIST, "normalized")
        terms = [Term('name_stemmed', q.text) for q in WhooshConstants.stem_analyzer(w)]
        query_stemmed = And(terms)
        terms = [fuzzy_term(q.text, self.DIST, "tokenized") for q in WhooshConstants.tokenized_analyzer(w)]
        query = Or([query_normalized, query_stemmed, And(terms)])
        with self.ix.searcher() as searcher:
            results = [Container({'name':r['name'], 'score':r.score}) for r in searcher.search(query, limit=40)]
            tag_first_if_relevant(results)
            return results

def tag_first_if_relevant(results):
    if len(results) == 0:
        return;
    if len(results) == 1:
        results[0]['relevant'] = True
        return
    scores = [el['score'] for el in results]
    a, b = itertools.tee(scores)
    next(b, None)
    diffs = [(i1 - i2) for i1, i2 in zip(a, b)]
    average = sum(diffs) / len(diffs)
    if diffs[0] / average >= 2:
        results[0]['relevant'] = True

def fuzzy_term(q, dist, field_suffix):
    if len(q) <= 3:
        return Term('name_{s}'.format(s=field_suffix), q)
    return FuzzyTerm('name_{s}'.format(s=field_suffix), q, maxdist=dist, prefixlength=1)
