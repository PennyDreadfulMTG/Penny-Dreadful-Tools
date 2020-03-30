from decksite.database import db
from magic import rotation
from shared import dtutil
from shared.pd_exception import DoesNotExistException


def run() -> None:
    existing = list(map(lambda s: s['number'], db().select('SELECT `number` FROM `season`;')))
    for season, setcode in enumerate(rotation.SEASONS, start=1):
        if not season in existing:
            try:
                info = rotation.get_set_info(setcode)
            except DoesNotExistException as e:
                print(f'Unable to get info for set with code `{setcode}` as it does not exist in rotatation data. Not inserting. {e}')
                continue
            if info.enter_date_dt < dtutil.now():
                print('Inserting {} into season table.'.format(setcode))
                db().execute('INSERT INTO season (`number`, code, start_date) VALUES (%s, %s, %s);', [season, setcode, dtutil.dt2ts(info.enter_date_dt)])
