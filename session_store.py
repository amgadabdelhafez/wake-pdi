"""Encrypted, bounded Portal-session records for unattended reconciliation.

The session record intentionally contains only the requests-session material
needed for the Developer Portal API. It is not a browser profile and it never
stores a browser cache, history, or saved form data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any

import requests
from cryptography.fernet import Fernet, InvalidToken

from config import ConfigurationError, get_key


SESSION_STORE_VERSION = 1
DEFAULT_SESSION_MAX_AGE_HOURS = 120


class SessionStoreError(RuntimeError):
    """Raised when an encrypted durable Portal session is unavailable."""


class SessionStoreExpired(SessionStoreError):
    """Raised when the operator-defined session-renewal bound has elapsed."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SessionStoreError("session record has no valid expiry timestamp")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise SessionStoreError("session record has no valid expiry timestamp") from error
    if parsed.tzinfo is None:
        raise SessionStoreError("session record expiry timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def _validated_session_max_age_hours(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SessionStoreError("session maximum age must be a positive integer number of hours")
    return value


def _cookie_expiry(cookie: Any) -> datetime | None:
    expires = getattr(cookie, "expires", None)
    if expires in (None, 0):
        return None
    try:
        return datetime.fromtimestamp(int(expires), tz=timezone.utc)
    except (OverflowError, OSError, TypeError, ValueError):
        return None


def _cookie_record(cookie: Any) -> dict[str, Any]:
    name = getattr(cookie, "name", None)
    value = getattr(cookie, "value", None)
    domain = getattr(cookie, "domain", None)
    if not all(isinstance(item, str) and item for item in (name, value, domain)):
        raise SessionStoreError("session contains an invalid cookie")
    path = getattr(cookie, "path", "/") or "/"
    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
        "secure": bool(getattr(cookie, "secure", False)),
        "expires": getattr(cookie, "expires", None),
    }


def session_record_from_requests_session(
    session: requests.Session,
    *,
    max_age_hours: int = DEFAULT_SESSION_MAX_AGE_HOURS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Capture a validated requests session without logging its token material."""
    max_age_hours = _validated_session_max_age_hours(max_age_hours)
    captured_at = now or utc_now()
    cookies = [_cookie_record(cookie) for cookie in session.cookies]
    if not cookies:
        raise SessionStoreError("refusing to persist a session without cookies")

    g_ck = getattr(session, "g_ck", None)
    if not isinstance(g_ck, str) or not g_ck:
        raise SessionStoreError("refusing to persist a session without a Developer Portal token")

    expires_at = captured_at + timedelta(hours=max_age_hours)
    cookie_expirations = [
        expiry for cookie in session.cookies if (expiry := _cookie_expiry(cookie)) is not None
    ]
    if cookie_expirations:
        expires_at = min(expires_at, *cookie_expirations)

    return {
        "captured_at": _as_utc_timestamp(captured_at),
        "expires_at": _as_utc_timestamp(expires_at),
        "g_ck": g_ck,
        "cookies": cookies,
    }


def _restore_requests_session(record: dict[str, Any]) -> requests.Session:
    cookies = record.get("cookies")
    g_ck = record.get("g_ck")
    if not isinstance(cookies, list) or not cookies:
        raise SessionStoreError("session record contains no cookies")
    if not isinstance(g_ck, str) or not g_ck:
        raise SessionStoreError("session record contains no Developer Portal token")

    session = requests.Session()
    for cookie in cookies:
        if not isinstance(cookie, dict):
            raise SessionStoreError("session record contains an invalid cookie")
        name = cookie.get("name")
        value = cookie.get("value")
        domain = cookie.get("domain")
        path = cookie.get("path", "/")
        if not all(isinstance(item, str) and item for item in (name, value, domain, path)):
            raise SessionStoreError("session record contains an invalid cookie")
        session.cookies.set(
            name,
            value,
            domain=domain,
            path=path,
            secure=bool(cookie.get("secure", False)),
            expires=cookie.get("expires"),
        )

    session.g_ck = g_ck
    session.magic_link = None
    session.processed_cookies = session.cookies.get_dict()
    session.processed_cookies["g_ck"] = g_ck
    session.processed_cookies["glide_user_token"] = g_ck
    return session


def _decode_store(encrypted_data: bytes) -> dict[str, Any]:
    try:
        decrypted = Fernet(get_key()).decrypt(encrypted_data)
        store = json.loads(decrypted.decode("utf-8"))
    except (
        ConfigurationError,
        InvalidToken,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise SessionStoreError("encrypted Portal session store is unreadable") from error
    if not isinstance(store, dict) or store.get("version") != SESSION_STORE_VERSION:
        raise SessionStoreError("encrypted Portal session store has an unsupported schema")
    if not isinstance(store.get("accounts"), dict):
        raise SessionStoreError("encrypted Portal session store has no account records")
    return store


def load_session_store(path: Path) -> dict[str, Any]:
    try:
        encrypted_data = path.read_bytes()
    except OSError as error:
        raise SessionStoreError("encrypted Portal session store is unavailable") from error
    return _decode_store(encrypted_data)


def write_session_store(path: Path, account_records: dict[str, dict[str, Any]]) -> None:
    """Persist an encrypted session record atomically with owner-only permissions."""
    encrypted_data = encrypt_session_store(account_records)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    try:
        descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encrypted_data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise SessionStoreError("unable to persist encrypted Portal session store") from error


def encrypt_session_store(account_records: dict[str, dict[str, Any]]) -> bytes:
    """Return an encrypted session store for a trusted in-memory handoff."""
    if not account_records:
        raise SessionStoreError("refusing to persist an empty Portal session store")
    store = {"version": SESSION_STORE_VERSION, "accounts": account_records}
    try:
        return Fernet(get_key()).encrypt(
            json.dumps(store, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    except (ConfigurationError, TypeError, ValueError) as error:
        raise SessionStoreError("unable to encrypt Portal session store") from error


def load_account_session(
    path: Path, account: str, *, now: datetime | None = None
) -> requests.Session:
    """Restore one unexpired account session or fail closed before Portal access."""
    store = load_session_store(path)
    record = store["accounts"].get(account)
    if not isinstance(record, dict):
        raise SessionStoreError("account has no durable Portal session")
    expires_at = _parse_utc_timestamp(record.get("expires_at"))
    if (now or utc_now()) >= expires_at:
        raise SessionStoreExpired("durable Portal session has expired and requires manual MFA renewal")
    try:
        return _restore_requests_session(record)
    except (TypeError, ValueError) as error:
        raise SessionStoreError("session record is not restorable") from error
