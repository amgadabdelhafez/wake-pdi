import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock, call, patch

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

    def test_mfa_code_prompt_submits_once_then_requires_portal_return(self):
        driver = Mock(current_url="https://accounts.google.com/signin/v2/challenge/totp")
        code_field = Mock()

        with (
            patch.dict(os.environ, {"CHROME_HEADLESS": "true"}, clear=False),
            patch.object(auth, "WebDriverWait") as wait,
            patch.object(auth, "_mfa_code_field", return_value=code_field),
            patch.object(auth, "prompt_for_mfa_code", return_value="123456") as prompt,
        ):
            wait.return_value.until.side_effect = ["mfa_code", "developer_portal"]

            self.assertTrue(auth.wait_for_login_completion(driver, mfa_code_prompt=True))

        prompt.assert_called_once_with()
        code_field.send_keys.assert_has_calls([call("123456"), call(auth.Keys.RETURN)])
        self.assertEqual(
            wait.call_args_list,
            [
                call(driver, auth.DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS),
                call(driver, auth.MFA_CODE_COMPLETION_TIMEOUT_SECONDS),
            ],
        )

    def test_mfa_code_prompt_repairs_the_known_post_auth_sso_landing(self):
        driver = Mock(current_url="https://accounts.google.com/signin/v2/challenge/totp")
        code_field = Mock()

        with (
            patch.dict(os.environ, {"CHROME_HEADLESS": "true"}, clear=False),
            patch.object(auth, "WebDriverWait") as wait,
            patch.object(auth, "_mfa_code_field", return_value=code_field),
            patch.object(auth, "prompt_for_mfa_code", return_value="123456"),
        ):
            wait.return_value.until.side_effect = ["mfa_code", "post_auth_sso", True]

            self.assertTrue(auth.wait_for_login_completion(driver, mfa_code_prompt=True))

        driver.get.assert_called_once_with(auth.DEVELOPER_PORTAL_URL)
        self.assertEqual(
            wait.call_args_list,
            [
                call(driver, auth.DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS),
                call(driver, auth.MFA_CODE_COMPLETION_TIMEOUT_SECONDS),
                call(driver, auth.POST_AUTH_PORTAL_CONTINUATION_TIMEOUT_SECONDS),
            ],
        )

    def test_local_totp_code_runs_the_local_helper_without_a_shell(self):
        completed = Mock(stdout="123456\n")
        passphrase_file = MagicMock()
        passphrase_file.__enter__.return_value = Path("/trusted/passphrase")

        with (
            patch.object(auth.shutil, "which", return_value="/trusted/mfa-vault-code") as which,
            patch.object(auth.subprocess, "run", return_value=completed) as run,
            patch.object(auth, "load_mfa_vault_passphrase", return_value=b"local-passphrase"),
            patch.object(
                auth, "temporary_mfa_vault_passphrase_file", return_value=passphrase_file
            ),
        ):
            code = auth.local_totp_code_for_account("user@example.invalid")

        self.assertEqual(code, "123456")
        which.assert_called_once_with(auth.MFA_TOTP_COMMAND)
        run.assert_called_once_with(
            ["/trusted/mfa-vault-code", "servicenow/user@example.invalid"],
            check=True,
            stdout=auth.subprocess.PIPE,
            stderr=auth.subprocess.DEVNULL,
            text=True,
            timeout=auth.MFA_TOTP_COMMAND_TIMEOUT_SECONDS,
            env={**os.environ, "MFA_VAULT_PASSPHRASE_FILE": "/trusted/passphrase"},
        )

    def test_local_totp_code_fails_closed_when_the_encrypted_passphrase_is_unavailable(self):
        with (
            patch.object(auth.shutil, "which") as which,
            patch.object(
                auth,
                "load_mfa_vault_passphrase",
                side_effect=auth.MfaVaultPassphraseError("unavailable"),
            ),
        ):
            self.assertIsNone(auth.local_totp_code_for_account("user@example.invalid"))

        which.assert_called_once_with(auth.MFA_TOTP_COMMAND)

    def test_local_totp_code_rejects_invalid_helper_output(self):
        passphrase_file = MagicMock()
        passphrase_file.__enter__.return_value = Path("/trusted/passphrase")
        with self.assertLogs(auth.logger, "ERROR") as logs:
            with (
                patch.object(auth.shutil, "which", return_value="/trusted/mfa-vault-code"),
                patch.object(auth.subprocess, "run", return_value=Mock(stdout="invalid-output\n")),
                patch.object(auth, "load_mfa_vault_passphrase", return_value=b"local-passphrase"),
                patch.object(
                    auth,
                    "temporary_mfa_vault_passphrase_file",
                    return_value=passphrase_file,
                ),
            ):
                self.assertIsNone(auth.local_totp_code_for_account("user@example.invalid"))

        self.assertNotIn("invalid-output", "\n".join(logs.output))

    def test_local_totp_code_fails_closed_when_the_helper_is_missing(self):
        with patch.object(auth.shutil, "which", return_value=None), patch.object(
            auth.subprocess, "run"
        ) as run:
            self.assertIsNone(auth.local_totp_code_for_account("user@example.invalid"))

        run.assert_not_called()

    def test_local_totp_code_fails_closed_when_the_helper_times_out(self):
        passphrase_file = MagicMock()
        passphrase_file.__enter__.return_value = Path("/trusted/passphrase")
        with (
            patch.object(auth.shutil, "which", return_value="/trusted/mfa-vault-code"),
            patch.object(
                auth.subprocess,
                "run",
                side_effect=auth.subprocess.TimeoutExpired("mfa-vault-code", 10),
            ),
            patch.object(auth, "load_mfa_vault_passphrase", return_value=b"local-passphrase"),
            patch.object(
                auth,
                "temporary_mfa_vault_passphrase_file",
                return_value=passphrase_file,
            ),
        ):
            self.assertIsNone(auth.local_totp_code_for_account("user@example.invalid"))

    def test_local_totp_code_rejects_an_unexpected_configured_identity(self):
        with patch.object(auth.shutil, "which") as which:
            self.assertIsNone(auth.local_totp_code_for_account("not-an-email"))

        which.assert_not_called()

    def test_totp_provider_submits_once_then_requires_portal_return(self):
        driver = Mock(current_url="https://accounts.google.com/signin/v2/challenge/totp")
        code_field = Mock()
        provider = Mock(return_value="123456")

        with (
            patch.dict(os.environ, {"CHROME_HEADLESS": "true"}, clear=False),
            patch.object(auth, "WebDriverWait") as wait,
            patch.object(auth, "_mfa_code_field", return_value=code_field),
        ):
            wait.return_value.until.side_effect = ["mfa_code", "developer_portal"]

            self.assertTrue(auth.wait_for_login_completion(driver, mfa_code_provider=provider))

        provider.assert_called_once_with()
        code_field.send_keys.assert_has_calls([call("123456"), call(auth.Keys.RETURN)])

    def test_totp_selects_authenticator_app_before_requesting_a_code(self):
        driver = Mock(current_url="https://accounts.google.com/signin/v2/challenge")
        option = Mock()
        code_field = Mock()
        provider = Mock(return_value="123456")

        with (
            patch.dict(os.environ, {"CHROME_HEADLESS": "true"}, clear=False),
            patch.object(auth, "WebDriverWait") as wait,
            patch.object(auth, "_authenticator_app_option", return_value=option),
            patch.object(auth, "_mfa_code_field", return_value=code_field),
        ):
            wait.return_value.until.side_effect = [
                "authenticator_app",
                "mfa_code",
                "developer_portal",
            ]

            self.assertTrue(
                auth.wait_for_login_completion(
                    driver,
                    mfa_code_provider=provider,
                    select_authenticator_app=True,
                )
            )

        option.click.assert_called_once_with()
        provider.assert_called_once_with()
        code_field.send_keys.assert_has_calls([call("123456"), call(auth.Keys.RETURN)])
        self.assertEqual(
            wait.call_args_list,
            [
                call(driver, auth.DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS),
                call(driver, auth.MFA_CODE_COMPLETION_TIMEOUT_SECONDS),
                call(driver, auth.MFA_CODE_COMPLETION_TIMEOUT_SECONDS),
            ],
        )

    def test_authenticator_app_option_refuses_unrecognized_identity_hosts(self):
        driver = Mock(current_url="https://untrusted.example.invalid/challenge")

        self.assertIsNone(auth._authenticator_app_option(driver))
        driver.find_elements.assert_not_called()

    def test_authenticator_app_option_targets_the_totp_factor_slug_first(self):
        driver = Mock(current_url="https://accounts.google.com/signin/v2/challenge")
        option = Mock()
        option.is_displayed.return_value = True
        option.is_enabled.return_value = True
        driver.find_elements.return_value = [option]

        self.assertIs(auth._authenticator_app_option(driver), option)
        driver.find_elements.assert_called_once_with(
            auth.By.CSS_SELECTOR,
            "#flyout-google_otp",
        )

    def test_login_completion_refuses_multiple_local_mfa_code_sources(self):
        driver = Mock()
        provider = Mock()

        with patch.object(auth, "WebDriverWait") as wait:
            self.assertFalse(
                auth.wait_for_login_completion(
                    driver,
                    mfa_code_prompt=True,
                    mfa_code_provider=provider,
                )
            )

        wait.assert_not_called()
        provider.assert_not_called()

    def test_login_completion_refuses_authenticator_selection_without_a_code_source(self):
        driver = Mock()

        with patch.object(auth, "WebDriverWait") as wait:
            self.assertFalse(
                auth.wait_for_login_completion(driver, select_authenticator_app=True)
            )

        wait.assert_not_called()

    def test_mfa_code_field_refuses_unrecognized_identity_hosts(self):
        driver = Mock(current_url="https://untrusted.example.invalid/challenge")

        self.assertIsNone(auth._mfa_code_field(driver))
        driver.find_elements.assert_not_called()

    def test_malformed_mfa_code_is_not_entered_or_logged(self):
        driver = Mock(current_url="https://accounts.google.com/signin/v2/challenge/totp")
        code_field = Mock()

        with patch.object(auth, "_mfa_code_field", return_value=code_field):
            self.assertFalse(auth._enter_mfa_code(driver, "not-a-code"))

        code_field.send_keys.assert_not_called()

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

    def test_do_sign_in_defers_totp_generation_to_login_completion(self):
        driver = Mock()
        account = {"sn_dev_username": "user@example.invalid", "sn_dev_password": "ciphertext"}

        with (
            patch.object(auth, "Fernet", FakeFernet),
            patch.object(auth, "get_key", return_value=b"test-key"),
            patch.object(auth, "setup_browser_driver", return_value=driver),
            patch.object(auth, "enter_credentials", return_value=True),
            patch.object(auth, "wait_for_login_completion", return_value=False) as wait,
            patch.object(auth, "handle_login_error", return_value="The Portal reported a sign-in error"),
            patch.object(auth.time, "sleep"),
        ):
            self.assertIsNone(auth.do_sign_in(account, mfa_totp=True))

        self.assertFalse(wait.call_args.kwargs["mfa_code_prompt"])
        self.assertIsNotNone(wait.call_args.kwargs["mfa_code_provider"])
        self.assertTrue(wait.call_args.kwargs["select_authenticator_app"])

    def test_do_sign_in_refuses_multiple_local_mfa_code_sources_before_decryption(self):
        account = {"sn_dev_username": "user@example.invalid", "sn_dev_password": "ciphertext"}

        with patch.object(auth, "Fernet") as fernet:
            self.assertIsNone(
                auth.do_sign_in(account, mfa_code_prompt=True, mfa_totp=True)
            )

        fernet.assert_not_called()


if __name__ == "__main__":
    unittest.main()
