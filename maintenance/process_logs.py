# This code forever tries to process logs with "casts" or "plays". Needs work if it is to be re-enabled. See analysis.py.
def ad_hoc() -> None:
    from analysis import analysis

    analysis.process_logs()
