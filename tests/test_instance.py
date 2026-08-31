import json
from unittest.mock import Mock
import unittest

import instance


class InstanceRequestTests(unittest.TestCase):
    def _session(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "result": {"instanceInfo": {"instanceStatus": {"state": "active"}}}
        }
        session = Mock()
        session.processed_cookies = {}
        session.get.return_value = response
        return session

    def test_status_query_keeps_direct_wake_disabled(self):
        session = self._session()
        result = instance.get_instance_info(session)

        self.assertEqual(result["instanceStatus"]["state"], "active")
        request_payload = json.loads(session.get.call_args.kwargs["params"]["sysparm_data"])
        self.assertFalse(request_payload["data"]["direct_wake_up"])
        self.assertEqual(session.get.call_args.kwargs["timeout"], instance.REQUEST_TIMEOUT_SECONDS)

    def test_wake_request_must_use_explicit_direct_wake(self):
        session = self._session()
        instance.wake_instance(session)

        request_payload = json.loads(session.get.call_args.kwargs["params"]["sysparm_data"])
        self.assertTrue(request_payload["data"]["direct_wake_up"])


if __name__ == "__main__":
    unittest.main()
