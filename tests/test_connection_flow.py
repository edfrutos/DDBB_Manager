import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog

from gui.main_window import MainWindow


class ConnectionFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.show_status_message = lambda *args, **kwargs: None
        self.window.show_collections = lambda: None
        self.window.update_database_stats = lambda: None
        self.window.tab_widget.setTabEnabled = lambda *args, **kwargs: None

    def test_initialize_connection_uses_env_database(self):
        calls = []
        self.window.connection_string = "mongodb://example.test:27017/"

        def fake_connect(connection_string, database_name):
            calls.append((connection_string, database_name))

        with patch.dict(os.environ, {"MONGODB_DATABASE": "catalogo"}, clear=False):
            self.window._connect_to_database = fake_connect
            self.window.initialize_connection()

        self.assertEqual(calls, [("mongodb://example.test:27017/", "catalogo")])

    def test_initialize_connection_is_noop_without_uri(self):
        calls = []
        self.window.connection_string = ""
        self.window._connect_to_database = lambda *args, **kwargs: calls.append("called")

        self.window.initialize_connection()

        self.assertEqual(calls, [])

    def test_initialize_connection_falls_back_to_saved_profile(self):
        calls = []
        self.window.connection_string = "mongodb+srv://invalid.example.test/"
        self.window.database_name = "catalogo"

        def fake_connect(connection_string, database_name):
            calls.append((connection_string, database_name))
            if connection_string == "mongodb+srv://invalid.example.test/":
                raise RuntimeError("DNS failure")

        with patch.object(self.window, "_load_saved_connection_profiles", return_value=[
            {"name": "saved", "uri": "mongodb://saved.example.test:27017/"}
        ]):
            self.window._connect_to_database = fake_connect
            self.window.initialize_connection()

        self.assertEqual(
            calls,
            [
                ("mongodb+srv://invalid.example.test/", "catalogo"),
                ("mongodb://saved.example.test:27017/", "catalogo"),
            ],
        )

    def test_open_connection_dialog_calls_connect_with_selected_data(self):
        calls = []

        class FakeDialog:
            def __init__(self, parent, connection_string):
                self.connection_string = connection_string

            def exec(self):
                return QDialog.DialogCode.Accepted

            def get_connection_data(self):
                return {
                    "connection_string": "mongodb://manual.test:27017/",
                    "database": "manual_db",
                }

        self.window.connection_string = "mongodb://initial.test:27017/"

        def fake_connect(connection_string, database_name):
            calls.append((connection_string, database_name))

        with patch("gui.main_window.ConnectionDialog", FakeDialog):
            self.window._connect_to_database = fake_connect
            self.window.open_connection_dialog()

        self.assertEqual(calls, [("mongodb://manual.test:27017/", "manual_db")])


if __name__ == "__main__":
    unittest.main()
