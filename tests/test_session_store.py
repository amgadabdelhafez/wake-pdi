from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from cryptography.fernet import Fernet
import requests

import session_store
import utils
import wake


class DurableSessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.key = Fernet.generate_key()
        self.now = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)

    def _session(self):
        session = requests.Session()
        session.cookies.set(
            "portal_session",
            "opaque-cookie",
            domain="developer.servicenow.com",
            path="/",
            secure=True,
        )
        session.g_ck = "opaque-portal-token"
        session.processed_cookies = {
            "portal_session": "opaque-cookie",
            "g_ck": "opaque-portal-token",
            "glide_user_token": "opaque-portal-token",
        }
        return session

    def test_round_trip_restores_an_unexpired_portal_session(self):
        session = self._session()
        record = session_store.session_record_from_requests_session(
            session, max_age_hours=120, now=self.now
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "portal_sessions.enc"
            with patch.object(session_store, "get_key", return_value=self.key):
                session_store.write_session_store(path, {"PDI_2": record})
                restored = session_store.load_account_session(
                    path, "PDI_2", now=self.now + timedelta(hours=1)
                )

        self.assertEqual(restored.processed_cookies["portal_session"], "opaque-cookie")
        self.assertEqual(restored.processed_cookies["g_ck"], "opaque-portal-token")
        self.assertEqual(restored.processed_cookies["glide_user_token"], "opaque-portal-token")

    def test_expired_session_refuses_portal_use(self):
        session = self._session()
        record = session_store.session_record_from_requests_session(
            session, max_age_hours=1, now=self.now
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "portal_sessions.enc"
            with patch.object(session_store, "get_key", return_value=self.key):
                session_store.write_session_store(path, {"PDI_2": record})
                with self.assertRaises(session_store.SessionStoreExpired):
                    session_store.load_account_session(
                        path, "PDI_2", now=self.now + timedelta(hours=1, seconds=1)
                    )

    def test_unreadable_store_fails_closed_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "portal_sessions.enc"
            path.write_bytes(b"not-an-encrypted-session")
            with patch.object(session_store, "get_key", return_value=b"not-a-fernet-key"):
                with self.assertRaises(session_store.SessionStoreError):
                    session_store.load_account_session(path, "PDI_2", now=self.now)

    def test_capture_refuses_session_without_portal_token(self):
        session = requests.Session()
        session.cookies.set("portal_session", "opaque", domain="developer.servicenow.com")

        with self.assertRaises(session_store.SessionStoreError):
            session_store.session_record_from_requests_session(session, now=self.now)

    def test_durable_only_mode_never_falls_back_to_browser_sign_in(self):
        browser_sign_in = Mock()
        unavailable = Mock(side_effect=session_store.SessionStoreExpired("expired"))

        session = wake._session_for_account(
            1,
            "PDI_2",
            {"sn_dev_username": "user@example.invalid"},
            durable_session_only=True,
            session_file=Path("/unavailable/portal_sessions.enc"),
            do_sign_in=browser_sign_in,
            load_account_session=unavailable,
        )

        self.assertIsNone(session)
        unavailable.assert_called_once()
        browser_sign_in.assert_not_called()

    def test_partial_capture_never_overwrites_an_existing_session_store(self):
        session = self._session()
        do_sign_in = Mock(side_effect=[session, None])
        get_instance_info = Mock(return_value={"instanceStatus": {"state": "active"}})
        args = {"session_file": "/tmp/portal_sessions.enc", "session_max_age_hours": 120}

        with patch("session_store.get_key", return_value=self.key), patch(
            "session_store.write_session_store"
        ) as write_store:
            result = wake._capture_durable_sessions(
                {
                    "PDI_2": {"sn_dev_username": "one@example.invalid"},
                    "PDI_3": {"sn_dev_username": "two@example.invalid"},
                },
                args,
                do_sign_in,
                get_instance_info,
            )

        self.assertEqual(result, 1)
        write_store.assert_not_called()

    def test_capture_stdout_encrypts_the_complete_store_without_a_local_write(self):
        session = self._session()
        output = SimpleNamespace(buffer=io.BytesIO())
        args = {"capture_sessions_stdout": True, "session_max_age_hours": 120}

        with patch("session_store.get_key", return_value=self.key), patch(
            "session_store.write_session_store"
        ) as write_store, patch.object(wake.sys, "stdout", output):
            result = wake._capture_durable_sessions(
                {"PDI_2": {"sn_dev_username": "one@example.invalid"}},
                args,
                Mock(return_value=session),
                Mock(return_value={"instanceStatus": {"state": "active"}}),
            )

        self.assertEqual(result, 0)
        write_store.assert_not_called()
        with patch.object(session_store, "get_key", return_value=self.key):
            self.assertEqual(
                set(session_store._decode_store(output.buffer.getvalue())["accounts"]),
                {"PDI_2"},
            )

    def test_capture_cli_requires_a_visible_browser_and_explicit_store_path(self):
        with patch.object(
            sys,
            "argv",
            ["wake.py", "--capture-sessions", "--not-headless", "--session-file", "/trusted/store"],
        ):
            args = utils.get_args()

        self.assertTrue(args["capture_sessions"])
        self.assertEqual(args["session_file"], "/trusted/store")
        self.assertEqual(args["session_max_age_hours"], 120)

        with patch.object(
            sys,
            "argv",
            ["wake.py", "--capture-sessions", "--capture-sessions-stdout", "--not-headless"],
        ):
            args = utils.get_args()

        self.assertTrue(args["capture_sessions_stdout"])
        self.assertIsNone(args["session_file"])

        with patch.object(sys, "argv", ["wake.py", "--capture-sessions", "--session-file", "/trusted/store"]):
            with self.assertRaises(SystemExit):
                utils.get_args()

        with patch.object(
            sys,
            "argv",
            [
                "wake.py",
                "--capture-sessions",
                "--capture-sessions-stdout",
                "--not-headless",
                "--session-file",
                "/trusted/store",
            ],
        ):
            with self.assertRaises(SystemExit):
                utils.get_args()


if __name__ == "__main__":
    unittest.main()
