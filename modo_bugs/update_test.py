import datetime
from types import SimpleNamespace

from modo_bugs import update


def test_age_in_days_handles_pygithub_aware_datetimes() -> None:
    """PyGithub 2.x returns tz-aware datetimes. A naive now() minus one of those is a TypeError, which took down every issue in update.main()."""
    issue = SimpleNamespace(updated_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7, hours=1))
    assert update.age_in_days(issue) == 7  # type: ignore[arg-type]
