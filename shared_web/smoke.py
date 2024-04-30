from typing import Any

from shared_web.flask_app import PDFlask


class SmokeTester:
    def __init__(self, app: PDFlask) -> None:
        self.app = app
        self.test_client = self.app.test_client()
        # Propagate the exceptions to the test client
        self.test_client.testing = True  # type: ignore

    def run(self) -> None:
        self.test_base()
        self.test_trailing_slashes()

    def test_base(self) -> None:
        self.response_test('/', 200)
        self.response_test('/doesnotexist', 404)

    def data_test(self, path: str, expected: str) -> None:
        result = self.test_client.get(path)
        assert expected in result.data.decode('utf-8')

    def response_test(self, path: str, expected_code: int) -> None:
        result = self.test_client.get(path)
        assert result.status_code == expected_code

    @property
    def url_map(self) -> Any:
        return self.test_client.application.url_map

    def test_trailing_slashes(self) -> None:
        api_endpoints = {}
        with self.app.app_context():
            for rule in self.url_map.iter_rules():
                rule_path = rule.rule
                assert '//' not in rule_path
                # Endpoints like "favicon.ico" and "robots.txt" should not have a trailing slash. Endpoints that serve files should not have a trailing slash. In some cases this makes them not work and in call cases it is ugly.
                if '.' in rule_path or ':filename>' in rule_path or 'favicon' in rule_path or rule_path.endswith('/oembed') or rule_path == '/export/<match_id>':
                    assert not rule_path.endswith('/')
                # API endpoints should have routes both with and without a trailing slash. This is partly for historical reasons and partly just so API clients can't "get it wrong" and experience unexpected redirects or 404s.
                elif rule_path.startswith('/api/') and rule_path != '/api/':  # /api/ itself is docs, not an API endpoint, and should have the same behavior as "normal" routes
                    api_endpoints[rule_path] = rule.methods
                # All "normal" routes should end with a trailing slash to get Flask's behavior of treating with trailing slash as canonical and without trailing slash as a redirect to the canonical.
                else:
                    assert rule_path.endswith('/')
        # Make sure each API endpoint has a route without a trailing slash and a route with a trailing slash so whatever the client programmer does, it works
        for rule_path in api_endpoints:
            if rule_path.endswith('/'):
                assert api_endpoints.get(rule_path.rstrip('/')) == api_endpoints.get(rule_path)
            else:
                assert api_endpoints.get(rule_path + '/') == api_endpoints.get(rule_path)
