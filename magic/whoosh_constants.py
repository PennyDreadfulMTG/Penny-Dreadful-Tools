from whoosh.analysis import IDTokenizer, LowercaseFilter, StandardAnalyzer, StemmingAnalyzer, SubstitutionFilter

from shared import configuration


class WhooshConstants:
    index_dir = configuration.get_str('whoosh_index_dir')
    tokenized_analyzer = StandardAnalyzer(stoplist=None)
    normalized_analyzer = IDTokenizer() | SubstitutionFilter('[\\s/,_\'"“”-]', '') | LowercaseFilter()
    stem_analyzer = StemmingAnalyzer('[\\s/,_\'"“”-]', gaps=True, stoplist=None)
