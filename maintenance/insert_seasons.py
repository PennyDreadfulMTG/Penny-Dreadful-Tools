from decksite.database import db
from magic import seasons
from shared import dtutil
from shared.pd_exception import DoesNotExistException

DAILY = True

def run() -> None:
    existing = list(map(lambda s: s['number'], db().select('SELECT `number` FROM `season`;')))
    for season, setcode in enumerate(seasons.SEASONS, start=1):
        if season not in existing:
            try:
                info = seasons.get_set_info(setcode)
            except DoesNotExistException as e:
                print(f'Unable to get info for set with code `{setcode}` as it does not exist in rotatation data. Not inserting. {e}')
                continue
            if info.enter_date_dt < dtutil.now():
                print(f'Inserting {setcode} into season table.')
                season_start = info.enter_date_dt + seasons.rotation_offset(info.code)
                db().execute('INSERT INTO season (`number`, code, start_date) VALUES (%s, %s, %s);', [season, setcode, dtutil.dt2ts(season_start)])
