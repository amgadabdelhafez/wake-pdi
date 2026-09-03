"""Non-secret state and policy helpers for the daily WakePDI reconciler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


STATE_VERSION = 1
FAILED_WAKE_RETRY_DELAY = timedelta(hours=24)
INACTIVE_STATES = {"", "expired", "first_time", "none", "unassigned"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def account_identifier(account_name: str) -> str:
    """Return a stable opaque account identifier suitable for persisted scheduler state."""
    return hashlib.sha256(account_name.encode("utf-8")).hexdigest()[:24]


def _value(instance_info: dict[str, Any], key: str) -> str:
    nested = instance_info.get("instanceStatus")
    value = instance_info.get(key)
    if value is None and isinstance(nested, dict):
        value = nested.get(key)
    return str(value or "").strip()


def status_summary(instance_info: dict[str, Any]) -> dict[str, str]:
    return {
        "state": _value(instance_info, "state"),
        "display_state": _value(instance_info, "display_state"),
    }


def is_active_assigned_pdi(instance_info: dict[str, Any]) -> bool:
    summary = status_summary(instance_info)
    state = summary["state"].lower()
    display_state = summary["display_state"].lower()
    if state in INACTIVE_STATES:
        return False
    if "no instance assigned" in display_state or "no active instance" in display_state:
        return False
    return bool(state or display_state)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


class ScheduleState:
    def __init__(self, path: Path, payload: dict[str, Any]):
        self.path = path
        self.payload = payload

    @classmethod
    def load(cls, path: str) -> "ScheduleState":
        state_path = Path(path)
        if not state_path.exists():
            return cls(state_path, {"version": STATE_VERSION, "accounts": {}})
        try:
            with open(state_path, "r", encoding="utf-8") as state_handle:
                payload = json.load(state_handle)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"unable to load scheduler state: {state_path}") from error
        if payload.get("version") != STATE_VERSION or not isinstance(payload.get("accounts"), dict):
            raise RuntimeError(f"unsupported scheduler state format: {state_path}")
        return cls(state_path, payload)

    def _entry(self, account_name: str) -> dict[str, Any]:
        identifier = account_identifier(account_name)
        accounts = self.payload["accounts"]
        return accounts.setdefault(identifier, {})

    def record_status(self, account_name: str, summary: dict[str, str], now: datetime) -> None:
        entry = self._entry(account_name)
        entry["last_status_at"] = now.isoformat()
        entry["last_observed_state"] = summary["state"]
        entry["last_observed_display_state"] = summary["display_state"]

    def record_wake_attempt(self, account_name: str, now: datetime) -> None:
        self._entry(account_name)["last_wake_attempt_at"] = now.isoformat()

    def record_wake_accepted(self, account_name: str, now: datetime) -> None:
        self._entry(account_name)["last_wake_accepted_at"] = now.isoformat()

    def record_extend_attempt(self, account_name: str, now: datetime) -> None:
        self._entry(account_name)["last_extend_attempt_at"] = now.isoformat()

    def record_extend_accepted(self, account_name: str, now: datetime) -> None:
        self._entry(account_name)["last_extend_accepted_at"] = now.isoformat()

    def extend_due(
        self,
        account_name: str,
        now: datetime,
        interval_hours: int,
        remaining_inactivity_days,
        threshold_days: int,
    ) -> tuple[bool, str]:
        """Extend only when the inactivity clock is genuinely low.

        Extend resets the inactivity timer, so it is pointless while the timer is near full.
        Due requires: a numeric remaining-inactivity reading at or below ``threshold_days``,
        the failed-attempt cool-off cleared, and the min interval since the last acceptance.
        """
        if remaining_inactivity_days is None:
            return False, "remaining inactivity days is unknown"
        try:
            remaining = float(remaining_inactivity_days)
        except (TypeError, ValueError):
            return False, "remaining inactivity days is not numeric"
        if remaining > threshold_days:
            return False, (
                f"{remaining:g} inactivity days remain (extend threshold {threshold_days})"
            )
        entry = self._entry(account_name)
        attempted_at = _parse_timestamp(entry.get("last_extend_attempt_at"))
        if attempted_at and now - attempted_at < FAILED_WAKE_RETRY_DELAY:
            return False, "an extend attempt is awaiting the next daily status check"
        accepted_at = _parse_timestamp(entry.get("last_extend_accepted_at"))
        if accepted_at is None:
            return True, f"{remaining:g} inactivity days remain and no prior extend is recorded"
        due_at = accepted_at + timedelta(hours=interval_hours)
        if now >= due_at:
            return True, f"{remaining:g} inactivity days remain and the extend interval has elapsed"
        return False, f"next extend eligible at {due_at.isoformat()}"

    def wake_due(
        self, account_name: str, now: datetime, interval_hours: int
    ) -> tuple[bool, str]:
        entry = self._entry(account_name)
        accepted_at = _parse_timestamp(entry.get("last_wake_accepted_at"))
        attempted_at = _parse_timestamp(entry.get("last_wake_attempt_at"))
        if attempted_at and now - attempted_at < FAILED_WAKE_RETRY_DELAY:
            return False, "a wake attempt is awaiting the next daily status check"
        if accepted_at is None:
            return True, "no prior Portal-accepted wake is recorded"
        due_at = accepted_at + timedelta(hours=interval_hours)
        if now >= due_at:
            return True, "the configured wake interval has elapsed"
        return False, f"next wake eligible at {due_at.isoformat()}"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(
            dir=self.path.parent, prefix=".schedule-state-", text=True
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as state_handle:
                os.fchmod(state_handle.fileno(), 0o600)
                json.dump(self.payload, state_handle, indent=2, sort_keys=True)
                state_handle.write("\n")
                state_handle.flush()
                os.fsync(state_handle.fileno())
            os.replace(temporary_path, self.path)
            os.chmod(self.path, 0o600)
        except Exception:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
            raise
