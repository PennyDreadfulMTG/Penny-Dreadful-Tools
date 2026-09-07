import datetime
from types import SimpleNamespace

import pytest

from modo_bugs import update


class FakeIssue:
    def __init__(self, title: str, labels: list[str]) -> None:
        self.title = title
        self.labels = [SimpleNamespace(name=label) for label in labels]
        self.body = ''
        self.updated_at = datetime.datetime.now(datetime.UTC)
        self.comments = [object()]
        self.number = 1
        self.actions: list[tuple[str, object]] = []

    def add_to_labels(self, label: str) -> None:
        self.actions.append(('add', label))

    def remove_from_labels(self, label: str) -> None:
        self.actions.append(('remove', label))

    def edit(self, **kwargs: object) -> None:
        self.actions.append(('edit', kwargs))

    def create_comment(self, body: str) -> None:
        self.actions.append(('comment', body))


def test_age_in_days_handles_pygithub_aware_datetimes() -> None:
    """PyGithub 2.x returns tz-aware datetimes. A naive now() minus one of those is a TypeError, which took down every issue in update.main()."""
    issue = SimpleNamespace(updated_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7, hours=1))
    assert update.age_in_days(issue) == 7  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ('title', 'labels', 'expected_actions'),
    [
        ('x' * 121, ['Advantageous'], [('add', 'Invalid Title')]),
        ('x' * 120, ['Advantageous', 'Invalid Title'], [('remove', 'Invalid Title')]),
        ('A concise title', ['Advantageous', 'Graphical'], [('add', 'Multiple Categories')]),
        ('A concise title', ['Advantageous', 'Non-Functional ability', 'Multiple Categories'], [('remove', 'Multiple Categories')]),
    ],
)
def test_check_for_invalid_metadata(title: str, labels: list[str], expected_actions: list[tuple[str, str]]) -> None:
    issue = FakeIssue(title, labels)

    update.check_for_invalid_metadata(issue)  # type: ignore[arg-type]

    assert issue.actions == expected_actions


def test_process_issue_checks_old_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    issue = FakeIssue('x' * 121, ['Advantageous'])
    issue.updated_at -= datetime.timedelta(days=365)
    monkeypatch.setattr(update, 'pd_legal_cards', lambda: [])

    update.process_issue(issue)  # type: ignore[arg-type]

    assert ('add', 'Invalid Title') in issue.actions
