import datetime

from shared import dtutil
from shared.container import Container


def friendly_date(dt: datetime.datetime, granularity: int = 1) -> Container:
    """Return the visible relative date and its exact machine-readable value for web views."""
    return Container({
        'datetime': dt.isoformat(),
        'display': dtutil.display_date(dt, granularity),
    })
