import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog

from gui.main_window import MainWindow
import gui.mixins.database_management as db_mixin
import gui.mixins.maintenance as maintenance_mixin


class FakeCursor(list):
    def limit(self, count):
        return FakeCursor(self[:count])


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []

    def insert_one(self, document):
        self.docs.append(document)
        return SimpleNamespace(inserted_id=len(self.docs))

    def insert_many(self, documents):
        self.docs.extend(documents)
        return SimpleNamespace(inserted_ids=list(range(1, len(documents) + 1)))

    def find(self, query=None, projection=None):
        query = query or {}
        if not query:
            return FakeCursor(self.docs[:])
        results = []
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                results.append(doc)
        return FakeCursor(results)

    def find_one(self, query=None, sort=None):
        results = list(self.find(query))
        if not results:
            return None
        return results[0]

    def count_documents(self, query):
        return len(list(self.find(query)))

    def list_indexes(self):
        return []

    def delete_one(self, query):
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not all(doc.get(key) == value for key, value in query.items())]
        return SimpleNamespace(deleted_count=before - len(self.docs))

    def delete_many(self, query):
        return self.delete_one(query)

    def validate(self):
        return {"valid": True}


class FakeDB:
    def __init__(self):
        self._collections = {}

    def list_collection_names(self):
        return list(self._collections.keys())

    def create_collection(self, name, **options):
        self._collections.setdefault(name, FakeCollection(name))
        return self._collections[name]

    def drop_collection(self, name):
        self._collections.pop(name, None)

    def command(self, cmd, collection_name):
        if cmd == "validate":
            return {"valid": True}
        if cmd == "collStats":
            return {"size": 1024, "avgObjSize": 128, "totalIndexSize": 0}
        raise ValueError(cmd)

    def __getitem__(self, name):
        return self._collections.setdefault(name, FakeCollection(name))


class SmokeFlowsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.db = FakeDB()
        self.window.client = object()
        self.window.database_name = "codex_smoke"
        self.window.show_collections = lambda: None
        self.window.update_database_stats = lambda: None
        if not hasattr(self.window, "query_editor") or self.window.query_editor is None:
            from PyQt6.QtWidgets import QTextEdit
            self.window.query_editor = QTextEdit()
        if not hasattr(self.window, "results_view") or self.window.results_view is None:
            from PyQt6.QtWidgets import QTextEdit
            self.window.results_view = QTextEdit()

    def test_create_query_drop_and_integrity(self):
        created_name = "smoke_collection"

        class FakeText:
            def __init__(self, value):
                self._value = value

            def text(self):
                return self._value

        class FakeCreateDialog:
            def __init__(self, parent):
                self.name_input = FakeText(created_name)

            def exec(self):
                return True

        class FakeDropDialog:
            def __init__(self, parent, collections):
                self.collections = collections

            def exec(self):
                return True

            def get_selected_collection(self):
                return created_name

        with patch.object(db_mixin, "CreateCollectionDialog", FakeCreateDialog), \
             patch.object(db_mixin, "DropCollectionDialog", FakeDropDialog), \
             patch.object(db_mixin.QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(maintenance_mixin.QDialog, "exec", return_value=0):

            self.window.create_collection()
            self.assertIn(created_name, self.window.db.list_collection_names())

            self.window.db[created_name].insert_one({"name": "codex-smoke", "value": 1})
            self.window.query_editor.setPlainText(f"db.{created_name}.find({{}})")
            self.window.execute_query()
            self.assertIn("codex-smoke", self.window.results_view.toPlainText())

            self.window.verify_integrity()
            self.window.drop_collection()
            self.assertNotIn(created_name, self.window.db.list_collection_names())


if __name__ == "__main__":
    unittest.main()
