from whoosh.analysis import IDTokenizer
from whoosh.analysis import SubstitutionFilter
from whoosh.analysis import LowercaseFilter
from whoosh.analysis import StandardAnalyzer
from whoosh.analysis import StemmingAnalyzer
from shared import configuration

class WhooshConstants():
    index_dir = configuration.get('whoosh_index_dir')
    tokenized_analyzer = StandardAnalyzer(stoplist=None)
    normalized_analyzer = IDTokenizer() | SubstitutionFilter(r"[\s/,_'-]", "") | LowercaseFilter()
    stem_analyzer = StemmingAnalyzer(r"[\s/,_'-]", gaps=True, stoplist=None)
