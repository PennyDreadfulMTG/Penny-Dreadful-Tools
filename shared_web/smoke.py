from shared_web.flask_app import PDFlask


class SmokeTester:
    def __init__(self, app: PDFlask) -> None:
        self.test_client = app.test_client()
        # Propagate the exceptions to the test client
        self.test_client.testing = True  # type: ignore
        self.base_tests()

    def base_tests(self) -> None:
        self.response_test('/', 200)
        self.response_test('/doesnotexist', 404)

    def data_test(self, path: str, expected: str) -> None:
        result = self.test_client.get(path) # type: ignore
        assert expected in result.data.decode('utf-8')

    def response_test(self, path: str, expected_code: int) -> None:
        result = self.test_client.get(path) # type: ignore
        assert result.status_code == expected_code
