from typing import Any, cast

import pytest

from decksite.controllers import admin
from decksite.main import APP
from decksite.views import EditRules


def test_all_admin_routes_require_permission() -> None:
    unprotected_routes = sorted({
        rule.rule
        for rule in APP.url_map.iter_rules()
        if rule.rule.startswith('/admin') and getattr(APP.view_functions[rule.endpoint], 'permission_required', None) not in {'admin', 'demimod'}
    })
    assert unprotected_routes == []


@pytest.mark.parametrize('path', ['/admin/banners/', '/admin/prizes/', '/admin/rotation/'])
def test_admin_information_pages_require_login(path: str) -> None:
    response = APP.test_client().get(path)
    assert response.status_code == 302
    assert response.location is not None
    assert response.location.startswith('/authenticate/?target=')


def test_post_rules_requires_archetype(monkeypatch: pytest.MonkeyPatch) -> None:
    def edit_rules(errors: list[str] | None = None) -> str:
        return EditRules(0, 0, [], [], [], [], [], [], errors).render_content()

    monkeypatch.setattr(admin, 'edit_rules', edit_rules)
    with APP.test_request_context('/admin/rules/', method='POST', data={'archetype_id': '', 'include': '4 Lightning Bolt'}):
        response = cast(Any, admin.post_rules).__wrapped__()
    assert 'Please select an archetype.' in response
    assert '<select name="archetype_id" required class="error" aria-describedby="archetype-error">' in response
