from analysis import analysis


# This code forever tries to process logs with "casts" or "plays". Needs work if it is to be re-enabled. See analysis.py.
def ad_hoc() -> None:
    analysis.process_logs()
