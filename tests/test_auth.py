import os
import unittest
from unittest.mock import Mock, call, patch

import auth


class FakeFernet:
    def __init__(self, _key):
        pass

    def decrypt(self, _value):
        return b"not-a-real-password"


class BrowserAuthenticationTests(unittest.TestCase):
    def test_visible_browser_uses_bounded_interactive_login_window(self):
        driver = Mock()
        with (
            patch.dict(os.environ, {"CHROME_HEADLESS": "false"}, clear=False),
            patch.object(auth, "WebDriverWait") as wait,
        ):
            wait.return_value.until.return_value = "developer_portal"

            self.assertTrue(auth.wait_for_login_completion(driver))

        wait.assert_called_once_with(
            driver, auth.INTERACTIVE_LOGIN_COMPLETION_TIMEOUT_SECONDS
        )

    def test_invalid_timeout_override_keeps_unattended_default(self):
        driver = Mock()
        with (
            patch.dict(
                os.environ,
                {
                    "CHROME_HEADLESS": "true",
                    "WAKE_PDI_LOGIN_COMPLETION_TIMEOUT_SECONDS": "invalid",
                },
                clear=False,
            ),
            patch.object(auth, "WebDriverWait") as wait,
        ):
            wait.return_value.until.return_value = "developer_portal"

            self.assertTrue(auth.wait_for_login_completion(driver))

        wait.assert_called_once_with(
            driver, auth.DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS
        )

    def test_post_auth_sso_landing_requests_bounded_portal_continuation(self):
        driver = Mock(current_url="https://signon.service-now.com/sso")
        driver.find_elements.return_value = []

        with patch.object(auth, "WebDriverWait") as wait:
            wait.return_value.until.side_effect = ["post_auth_sso", True]

            self.assertTrue(auth.wait_for_login_completion(driver))

        driver.get.assert_called_once_with(auth.DEVELOPER_PORTAL_URL)
        self.assertEqual(
            wait.call_args_list,
            [
                call(driver, auth.DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS),
                call(driver, auth.POST_AUTH_PORTAL_CONTINUATION_TIMEOUT_SECONDS),
            ],
        )

    def test_browser_location_diagnostic_removes_query_values(self):
        driver = Mock(current_url="https://login.example.invalid/sign-in?token=do-not-log")

        self.assertEqual(auth._safe_browser_location(driver), "login.example.invalid/sign-in")

    def test_browser_form_state_diagnostic_never_reads_control_values(self):
        visible_username = Mock()
        visible_username.is_displayed.return_value = True

        def elements_for(_by, identifier):
            return [visible_username] if identifier == "username" else []

        driver = Mock()
        driver.find_elements.side_effect = elements_for

        self.assertEqual(
            auth._safe_browser_form_state(driver),
            "controls=username;iframe=False",
        )

    def test_does_not_create_a_session_when_portal_return_is_not_confirmed(self):
        driver = Mock()
        account = {"sn_dev_username": "user@example.invalid", "sn_dev_password": "ciphertext"}

        with (
            patch.object(auth, "Fernet", FakeFernet),
            patch.object(auth, "get_key", return_value=b"test-key"),
            patch.object(auth, "setup_browser_driver", return_value=driver),
            patch.object(auth, "enter_credentials", return_value=True),
            patch.object(auth, "wait_for_login_completion", return_value=False),
            patch.object(auth, "handle_login_error", return_value="The Portal reported a sign-in error"),
            patch.object(auth, "create_session_from_cookies") as create_session,
            patch.object(auth.time, "sleep") as sleep,
        ):
            result = auth.do_sign_in(account)

        self.assertIsNone(result)
        self.assertIn("signon.servicenow.com/x_snc_sso_auth.do", driver.get.call_args.args[0])
        create_session.assert_not_called()
        driver.quit.assert_called_once_with()
        sleep.assert_called_once_with(auth.PORTAL_LOGIN_TRANSITION_SECONDS)


if __name__ == "__main__":
    unittest.main()
