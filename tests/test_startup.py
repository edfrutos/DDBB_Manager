import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

import main_gui


class StartupFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_build_application_reuses_qapplication_and_sets_metadata(self):
        app = main_gui.build_application([])

        self.assertIs(app, QApplication.instance())
        self.assertEqual(app.applicationName(), "Gestor de Base de Datos MongoDB")
        self.assertEqual(app.applicationVersion(), "1.0.0")

    def test_schedule_autoconnect_with_uri_queues_callback(self):
        calls = []

        class FakeWindow:
            def initialize_connection(self):
                calls.append("initialize")

        def fake_timer(delay_ms, callback):
            calls.append(("timer", delay_ms))
            callback()

        scheduled = main_gui.schedule_autoconnect(FakeWindow(), "mongodb://localhost:27017/", delay_ms=123, timer_fn=fake_timer)

        self.assertTrue(scheduled)
        self.assertEqual(calls[0], ("timer", 123))
        self.assertEqual(calls[1], "initialize")

    def test_schedule_autoconnect_without_uri_is_noop(self):
        calls = []

        def fake_timer(delay_ms, callback):
            calls.append(("timer", delay_ms))

        scheduled = main_gui.schedule_autoconnect(object(), "", delay_ms=123, timer_fn=fake_timer)

        self.assertFalse(scheduled)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
