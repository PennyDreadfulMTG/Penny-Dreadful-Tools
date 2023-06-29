from typing import TypedDict
from typing_extensions import NotRequired


class BugData(TypedDict):
    card: str
    description: str
    category: str
    issue_number: int
    last_updated: str
    pd_legal: bool
    bug_blog: bool
    breaking: bool
    bannable: bool
    url: str
    support_thread: str | None
    last_verified: str | None
    multiplayer_only: NotRequired[bool]
    commander_only: NotRequired[bool]
    cade_bug: NotRequired[bool]
    help_wanted: NotRequired[bool]

class ForumData(TypedDict):
    title: str
    url: str
    status: str
    tracked: bool
