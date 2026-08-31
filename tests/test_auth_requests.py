import unittest
from unittest.mock import patch

import auth_requests


class FakeResponse:
    def __init__(self, url, headers=None, status_code=200, text="", payload=None):
        self.url = url
        self.headers = headers or {}
        self.status_code = status_code
        self.text = text
        self.payload = payload or {}

    def json(self):
        return self.payload


class FakeCookies(dict):
    def get_dict(self):
        return dict(self)


class FakeSession:
    def __init__(self):
        self.cookies = FakeCookies({"portal_session": "opaque"})
        self.get_responses = [
            FakeResponse("https://developer.servicenow.com/dev.do"),
            FakeResponse("https://signon.service-now.com/ssologin.do"),
            FakeResponse(
                "https://developer.servicenow.com/dev.do",
                headers={"X-UserToken": "test-token"},
            ),
            FakeResponse(
                "https://developer.servicenow.com/api/snc/v1/dev/instanceInfo",
                payload={"result": {"data": {"is_guest_user": False}}},
            ),
        ]
        self.get_calls = []
        self.post_calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.get_responses.pop(0)

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse("https://signon.service-now.com/ssologin.do")

    def close(self):
        self.closed = True


class FakeFernet:
    def __init__(self, _key):
        pass

    def decrypt(self, _value):
        return b"not-a-real-password"


class RequestsAuthenticationTests(unittest.TestCase):
    def test_returns_portal_compatible_session_without_persisting_tokens(self):
        session = FakeSession()
        with (
            patch.object(auth_requests.requests, "Session", return_value=session),
            patch.object(auth_requests, "Fernet", FakeFernet),
            patch.object(auth_requests, "get_key", return_value=b"test-key"),
            patch.object(auth_requests.time, "sleep"),
        ):
            result = auth_requests.do_sign_in_requests(
                {"sn_dev_username": "user@example.invalid", "sn_dev_password": "ciphertext"}
            )

        self.assertIs(result, session)
        self.assertEqual(session.processed_cookies["portal_session"], "opaque")
        self.assertEqual(session.processed_cookies["g_ck"], "test-token")
        self.assertEqual(session.processed_cookies["glide_user_token"], "test-token")
        self.assertEqual(len(session.post_calls), 2)
        self.assertFalse(session.closed)


if __name__ == "__main__":
    unittest.main()
