import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from scheduler import ScheduleState, account_identifier, is_active_assigned_pdi, status_summary


class SchedulerTests(unittest.TestCase):
    def test_inactive_portal_statuses_are_never_wakeable(self):
        self.assertFalse(
            is_active_assigned_pdi(
                {"instanceStatus": {"state": "first_time", "display_state": "No Instance Assigned"}}
            )
        )
        self.assertFalse(is_active_assigned_pdi({"state": "expired"}))

    def test_active_status_is_wakeable(self):
        info = {"instanceStatus": {"state": "active", "display_state": "Awake"}}
        self.assertTrue(is_active_assigned_pdi(info))
        self.assertEqual(status_summary(info), {"state": "active", "display_state": "Awake"})

    def test_wake_cadence_and_opaque_persistence(self):
        now = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "schedule-state.json"
            state = ScheduleState.load(str(state_path))
            self.assertEqual(
                state.wake_due("PDI_1", now, 96),
                (True, "no prior Portal-accepted wake is recorded"),
            )

            state.record_status("PDI_1", {"state": "active", "display_state": "Awake"}, now)
            state.record_wake_attempt("PDI_1", now)
            state.record_wake_accepted("PDI_1", now)
            state.save()

            persisted_text = state_path.read_text(encoding="utf-8")
            persisted = json.loads(persisted_text)
            self.assertIn(account_identifier("PDI_1"), persisted["accounts"])
            self.assertNotIn("PDI_1", persisted_text)

            reloaded = ScheduleState.load(str(state_path))
            self.assertFalse(reloaded.wake_due("PDI_1", now + timedelta(hours=95), 96)[0])
            self.assertTrue(reloaded.wake_due("PDI_1", now + timedelta(hours=96), 96)[0])


if __name__ == "__main__":
    unittest.main()
