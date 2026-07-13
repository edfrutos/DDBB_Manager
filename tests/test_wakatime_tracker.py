import os
import unittest
from unittest.mock import patch

from gui.wakatime import WakaTimeTracker


class WakaTimeTrackerTest(unittest.TestCase):
    def test_disabled_tracker_is_noop(self):
        tracker = WakaTimeTracker(api_key="waka_test", enabled=False)

        self.assertFalse(tracker.heartbeat("app_opened", sync=True))

    def test_builds_payload(self):
        tracker = WakaTimeTracker(api_key="waka_test", project_name="DDBB_Manager")

        payload = tracker.build_payload("execute_query", category="manual testing", type_="app", timestamp=123.45)

        self.assertEqual(payload["entity"], "execute_query")
        self.assertEqual(payload["type"], "app")
        self.assertEqual(payload["category"], "manual testing")
        self.assertEqual(payload["time"], 123.45)
        self.assertEqual(payload["project"], "DDBB_Manager")

    def test_sync_heartbeat_posts_to_wakatime(self):
        tracker = WakaTimeTracker(api_key="waka_test", project_name="DDBB_Manager")

        class FakeResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("gui.wakatime.urlopen", return_value=FakeResponse()) as mock_urlopen:
            result = tracker.heartbeat("app_opened", sync=True)

        self.assertTrue(result)
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_from_environment_requires_enable_flag_and_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(WakaTimeTracker.from_environment())

        with patch.dict(os.environ, {"WAKATIME_ENABLED": "1"}, clear=True):
            self.assertIsNone(WakaTimeTracker.from_environment())

        with patch.dict(
            os.environ,
            {"WAKATIME_ENABLED": "true", "WAKATIME_API_KEY": "waka_test", "WAKATIME_PROJECT_NAME": "DB"},
            clear=True,
        ):
            tracker = WakaTimeTracker.from_environment()

        self.assertIsNotNone(tracker)
        self.assertEqual(tracker.project_name, "DB")


if __name__ == "__main__":
    unittest.main()
