import datetime

from shared import human_time

def test_display_date():
    dt = datetime.datetime(2008, 3, 29)
    assert human_time.display_date(dt) == 'Mar 29, 2008'
    dt = datetime.datetime.now() - datetime.timedelta(seconds=10)
    assert human_time.display_date(dt).find('seconds') >= 0
