import unittest
from datetime import timedelta

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scheduler import ScheduleState, utc_now
import instance


class ExtendDueTests(unittest.TestCase):
    def _state(self, tmp):
        return ScheduleState.load(str(Path(tmp) / "state.json"))

    def test_not_due_when_inactivity_clock_is_full(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            s = self._state(tmp)
            due, reason = s.extend_due("PDI_1", utc_now(), 24, 10.0, 2)
            self.assertFalse(due)
            self.assertIn("inactivity days remain", reason)

    def test_due_when_below_threshold_and_no_prior_extend(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            s = self._state(tmp)
            due, reason = s.extend_due("PDI_1", utc_now(), 24, 1.0, 2)
            self.assertTrue(due)
            self.assertIn("no prior extend", reason)

    def test_unknown_or_nonnumeric_remaining_is_never_due(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            s = self._state(tmp)
            self.assertFalse(s.extend_due("PDI_1", utc_now(), 24, None, 2)[0])
            self.assertFalse(s.extend_due("PDI_1", utc_now(), 24, "n/a", 2)[0])

    def test_interval_and_failed_attempt_cooloff(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            s = self._state(tmp)
            now = utc_now()
            s.record_extend_attempt("PDI_1", now)
            # a fresh attempt blocks re-extend until the next daily status check
            self.assertFalse(s.extend_due("PDI_1", now, 24, 1.0, 2)[0])
            s.record_extend_accepted("PDI_1", now)
            self.assertFalse(s.extend_due("PDI_1", now + timedelta(hours=23), 24, 1.0, 2)[0])
            self.assertTrue(s.extend_due("PDI_1", now + timedelta(hours=24), 24, 1.0, 2)[0])

    def test_persistence_round_trip(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            s = ScheduleState.load(str(path))
            now = utc_now()
            s.record_extend_accepted("PDI_1", now)
            s.save()
            reloaded = ScheduleState.load(str(path))
            self.assertFalse(reloaded.extend_due("PDI_1", now + timedelta(hours=1), 24, 1.0, 2)[0])


class ExtendInstanceGuardTests(unittest.TestCase):
    def test_refuses_without_cat_item_id(self):
        self.assertIsNone(instance.extend_instance(object(), {"sys_id": "abc"}, None))
        self.assertIsNone(instance.extend_instance(object(), {"sys_id": "abc"}, ""))

    def test_refuses_without_instance_sys_id(self):
        self.assertIsNone(instance.extend_instance(object(), {}, "cat123"))

    def test_execute_cat_item_sends_supplied_id_only(self):
        captured = {}

        class FakeResp:
            status_code = 200

            def json(self):
                return {"result": {"status": "complete_success"}}

        class FakeSession:
            processed_cookies = {}

            def get(self, url, params=None, headers=None, timeout=None):
                captured["url"] = url
                captured["params"] = params
                return FakeResp()

        out = instance.extend_instance(FakeSession(), {"sys_id": "INS1"}, "CAT-EXTEND")
        self.assertEqual(out, {"status": "complete_success"})
        self.assertIn("execute_cat_item", captured["params"]["sysparm_data"])
        self.assertIn("INS1", captured["params"]["sysparm_data"])
        self.assertIn("CAT-EXTEND", captured["params"]["sysparm_data"])


if __name__ == "__main__":
    unittest.main()
