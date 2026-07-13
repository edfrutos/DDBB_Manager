import os
import json
import unittest
import tempfile
import hashlib
import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bson.objectid import ObjectId
from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog

from gui.main_window import MainWindow
import gui.mixins.database_management as db_mixin
import gui.mixins.backup as backup_mixin
import gui.mixins.import_export as import_export_mixin
import gui.mixins.collection_views as collection_views_mixin
import gui.mixins.maintenance as maintenance_mixin
import gui.mixins.user_management as user_mixin


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
            if self._matches(doc, query):
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
        return [{"name": "_id_", "key": {"_id": 1}}]

    def create_index(self, key, name=None):
        return name or "_id_"

    def delete_one(self, query):
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not all(doc.get(key) == value for key, value in query.items())]
        return SimpleNamespace(deleted_count=before - len(self.docs))

    def delete_many(self, query):
        return self.delete_one(query)

    def update_one(self, query, update):
        matched = 0
        modified = 0
        for doc in self.docs:
            if self._matches(doc, query):
                matched = 1
                set_fields = update.get("$set", {})
                before = {key: doc.get(key) for key in set_fields}
                doc.update(set_fields)
                if any(before.get(key) != doc.get(key) for key in set_fields):
                    modified = 1
                break
        return SimpleNamespace(matched_count=matched, modified_count=modified)

    def validate(self):
        return {"valid": True}

    def _matches(self, document, query):
        for key, value in query.items():
            if key == "$or":
                return any(self._matches(document, item) for item in value)
            if "." in key:
                current = document
                for part in key.split("."):
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        current = None
                        break
                if isinstance(value, dict):
                    if "$exists" in value:
                        if bool(value["$exists"]) != (current is not None):
                            return False
                        continue
                    if current != value:
                        return False
                else:
                    if current != value:
                        return False
                continue
            if isinstance(value, dict):
                if "$exists" in value:
                    if bool(value["$exists"]) != (key in document):
                        return False
                    continue
                if "$regex" in value:
                    current = str(document.get(key, ""))
                    expected = value["$regex"]
                    if value.get("$options") == "i":
                        if expected.lower() not in current.lower():
                            return False
                    elif expected not in current:
                        return False
                    continue
                if "$in" in value:
                    if document.get(key) not in value["$in"]:
                        return False
                    continue
                if document.get(key) != value:
                    return False
                continue
            if document.get(key) != value:
                return False
        return True


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


class FakeClient:
    def __init__(self, databases):
        self._databases = databases
        self.admin = SimpleNamespace(command=lambda _cmd: {"version": "8.0", "uptime": 86400, "connections": {"current": 1, "available": 99}})

    def list_database_names(self):
        return list(self._databases.keys())

    def __getitem__(self, name):
        return self._databases[name]


class FakeLabel:
    def __init__(self):
        self.text_value = ""

    def setText(self, value):
        self.text_value = value


class FakeTabs:
    def __init__(self):
        self.enabled = {1: False}
        self.current_index = None

    def isTabEnabled(self, index):
        return self.enabled.get(index, False)

    def setTabEnabled(self, index, enabled):
        self.enabled[index] = enabled

    def setCurrentIndex(self, index):
        self.current_index = index


class FakeUserLabel:
    def __init__(self):
        self.text_value = ""
        self.style_value = ""

    def setText(self, value):
        self.text_value = value

    def setStyleSheet(self, value):
        self.style_value = value


class FakeSearchType:
    def __init__(self, value):
        self._value = value

    def currentText(self):
        return self._value


class FakeToggleField:
    def __init__(self, value=""):
        self._value = value
        self.enabled = False

    def text(self):
        return self._value

    def setEnabled(self, value):
        self.enabled = value


class FakeButton:
    def __init__(self):
        self.enabled = False

    def setEnabled(self, value):
        self.enabled = value


class FakeLineEdit:
    def __init__(self, value=""):
        self._value = value

    def text(self):
        return self._value


class FakeComboBox:
    def __init__(self):
        self._items = []
        self._current = ""

    def addItems(self, items):
        self._items.extend(items)
        if not self._current and items:
            self._current = items[0]

    def setCurrentText(self, value):
        self._current = value

    def currentText(self):
        return self._current


class FakeImportDialog:
    def __init__(self, parent, collections, target_collection="target", clear=False):
        self.target_collection = target_collection
        self.clear = clear

    def exec(self):
        return True

    def get_target_collection(self):
        return self.target_collection

    def should_clear_collection(self):
        return self.clear


class FakeExportDialog:
    def __init__(self, parent, collections, collection_name="source", export_format="json"):
        self.collection_name = collection_name
        self.export_format = export_format

    def exec(self):
        return True

    def get_selected_collection(self):
        return self.collection_name

    def get_export_format(self):
        return self.export_format


class FakeTable:
    def __init__(self):
        self.rows = 0
        self.items = {}

    def setRowCount(self, count):
        self.rows = count

    def setItem(self, row, column, item):
        self.items[(row, column)] = item.text()

    def resizeColumnsToContents(self):
        pass


class FakeProgressDialog:
    def __init__(self, *args, **kwargs):
        self._canceled = False
        self._value = 0
        self._label = ""
        self.accepted = False

    def setWindowTitle(self, *_args, **_kwargs):
        pass

    def setWindowModality(self, *_args, **_kwargs):
        pass

    def setAutoClose(self, *_args, **_kwargs):
        pass

    def setAutoReset(self, *_args, **_kwargs):
        pass

    def setValue(self, value):
        self._value = value

    def setLabelText(self, text):
        self._label = text

    def show(self):
        pass

    def wasCanceled(self):
        return self._canceled


class FakeDialog:
    def __init__(self):
        self.accepted = False

    def accept(self):
        self.accepted = True

    def reject(self):
        self.accepted = False


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

    def test_switch_database_updates_state(self):
        primary_db = FakeDB()
        secondary_db = FakeDB()
        client = FakeClient({"codex_smoke": primary_db, "codex_target": secondary_db, "admin": FakeDB()})

        self.window.client = client
        self.window.db = primary_db
        self.window.database_name = "codex_smoke"
        self.window.connection_status_label = FakeLabel()
        self.window.tab_widget = FakeTabs()
        self.window.show_collections = lambda: None
        self.window.update_database_stats = lambda: None
        messages = []
        self.window.show_status_message = lambda message, error=False: messages.append((message, error))

        self.window.switch_to_database("codex_target")

        self.assertEqual(self.window.database_name, "codex_target")
        self.assertIs(self.window.db, secondary_db)
        self.assertEqual(self.window.connection_status_label.text_value, "Conectado a: codex_target")
        self.assertTrue(self.window.tab_widget.isTabEnabled(1))
        self.assertEqual(self.window.tab_widget.current_index, 1)
        self.assertIn(("Cambiado a la base de datos: codex_target", False), messages)

    def test_backup_and_restore_round_trip(self):
        source_db = FakeDB()
        source_db.create_collection("alpha")
        source_db["alpha"].insert_one({"_id": "a1", "name": "uno"})
        source_db.create_collection("beta")
        source_db["beta"].insert_one({"_id": "b1", "name": "dos"})

        target_db = FakeDB()
        self.window.client = FakeClient({"codex_smoke": source_db})
        self.window.db = source_db
        self.window.database_name = "codex_smoke"

        with tempfile.TemporaryDirectory() as tmpdir:
            dialog = FakeDialog()
            with patch.object(backup_mixin, "QProgressDialog", FakeProgressDialog), \
                 patch.object(backup_mixin.QMessageBox, "information", return_value=None), \
                 patch.object(backup_mixin.QMessageBox, "warning", return_value=None), \
                 patch.object(backup_mixin.QMessageBox, "critical", return_value=None):

                self.window.execute_backup(
                    tmpdir,
                    True,
                    [],
                    False,
                    6,
                    False,
                    "Diario",
                    None,
                    "Lunes",
                    dialog,
                )

            metadata = Path(tmpdir, "metadata.json")
            self.assertTrue(metadata.exists())
            self.assertTrue(Path(tmpdir, "collections", "alpha.json").exists())
            self.assertTrue(Path(tmpdir, "collections", "beta.json").exists())
            self.assertTrue(dialog.accepted)

            self.window.db = target_db
            self.window.database_name = "codex_smoke"
            restore_dialog = FakeDialog()
            with patch.object(backup_mixin, "QProgressDialog", FakeProgressDialog), \
                 patch.object(backup_mixin.QMessageBox, "information", return_value=None), \
                 patch.object(backup_mixin.QMessageBox, "warning", return_value=None), \
                 patch.object(backup_mixin.QMessageBox, "critical", return_value=None):

                metadata_data = json.loads(metadata.read_text(encoding="utf-8"))
                self.window.execute_restore(
                    tmpdir,
                    metadata_data,
                    True,
                    [],
                    2,
                    False,
                    restore_dialog,
                )

            self.assertIn("alpha", self.window.db.list_collection_names())
            self.assertIn("beta", self.window.db.list_collection_names())
            self.assertEqual(self.window.db["alpha"].find_one({"_id": "a1"})["name"], "uno")
            self.assertEqual(self.window.db["beta"].find_one({"_id": "b1"})["name"], "dos")

    def test_user_password_flow(self):
        user_id = "507f1f77bcf86cd799439011"
        self.window.db.create_collection("users_unified")
        self.window.db["users_unified"].insert_one({
            "_id": user_id,
            "nombre": "Ada Lovelace",
            "email": "ada@example.com",
            "role": "admin",
        })

        search_dialog = SimpleNamespace(
            search_text=FakeToggleField("Ada"),
            search_type=FakeSearchType("Por Nombre"),
            user_label=FakeUserLabel(),
            password_input=FakeToggleField(""),
            confirm_input=FakeToggleField(""),
            save_button=FakeButton(),
            selected_user=None,
            selected_collection=None,
        )

        with patch.object(user_mixin.QMessageBox, "warning", return_value=None), \
             patch.object(user_mixin.QMessageBox, "information", return_value=None), \
             patch.object(user_mixin.QMessageBox, "critical", return_value=None):
            self.window.search_user_for_password(search_dialog)

        self.assertIn("Ada Lovelace", search_dialog.user_label.text_value)
        self.assertTrue(search_dialog.password_input.enabled)
        self.assertTrue(search_dialog.confirm_input.enabled)
        self.assertTrue(search_dialog.save_button.enabled)
        self.assertEqual(search_dialog.selected_collection, "users_unified")
        self.assertIsNotNone(search_dialog.selected_user)

        password_dialog = SimpleNamespace(
            selected_user=search_dialog.selected_user,
            selected_collection="users_unified",
            password_input=FakeToggleField("supersecret"),
            confirm_input=FakeToggleField("supersecret"),
            accept=lambda: setattr(password_dialog, "accepted", True),
            accepted=False,
        )

        with patch.object(user_mixin.QMessageBox, "warning", return_value=None), \
             patch.object(user_mixin.QMessageBox, "information", return_value=None), \
             patch.object(user_mixin.QMessageBox, "critical", return_value=None):
            self.window.update_user_password(password_dialog)

        stored = self.window.db["users_unified"].find_one({"_id": user_id})
        self.assertEqual(stored["password"], hashlib.sha256("supersecret".encode()).hexdigest())
        self.assertIn("password_changed_at", stored)

    def test_import_export_json_round_trip(self):
        source = self.window.db.create_collection("source")
        source.insert_one({"_id": "1", "name": "uno"})
        source.insert_one({"_id": "2", "name": "dos"})

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir, "source.json")
            import_path = Path(tmpdir, "import.json")
            import_path.write_text(json.dumps([
                {"_id": "10", "name": "diez"},
                {"_id": "11", "name": "once"},
            ]), encoding="utf-8")

            with patch.object(import_export_mixin, "ExportDialog", lambda parent, collections: FakeExportDialog(parent, collections, "source", "json")), \
                 patch.object(import_export_mixin, "ImportDialog", lambda parent, collections: FakeImportDialog(parent, collections, "target", True)), \
                 patch.object(import_export_mixin.QFileDialog, "getSaveFileName", return_value=(str(export_path), "JSON Files (*.json)")), \
                 patch.object(import_export_mixin.QFileDialog, "getOpenFileName", return_value=(str(import_path), "JSON Files (*.json)")), \
                 patch.object(import_export_mixin.QMessageBox, "information", return_value=None), \
                 patch.object(import_export_mixin.QMessageBox, "warning", return_value=None), \
                 patch.object(import_export_mixin.QMessageBox, "critical", return_value=None):

                self.window.export_data()
                self.assertTrue(export_path.exists())
                exported = json.loads(export_path.read_text(encoding="utf-8"))
                self.assertEqual(len(exported), 2)
                self.assertEqual(exported[0]["name"], "uno")

                self.window.import_data()
                self.assertEqual(self.window.db["target"].count_documents({}), 2)
                self.assertEqual(self.window.db["target"].find_one({"_id": "10"})["name"], "diez")

    def test_import_export_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir, "people.csv")
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["_id", "name", "role"])
                writer.writeheader()
                writer.writerow({"_id": "1", "name": "Ada", "role": "admin"})
                writer.writerow({"_id": "2", "name": "Grace", "role": "user"})

            export_path = Path(tmpdir, "people_export.csv")

            with patch.object(import_export_mixin, "ImportDialog", lambda parent, collections: FakeImportDialog(parent, collections, "people", True)), \
                 patch.object(import_export_mixin, "ExportDialog", lambda parent, collections: FakeExportDialog(parent, collections, "people", "csv")), \
                 patch.object(import_export_mixin.QFileDialog, "getOpenFileName", return_value=(str(csv_path), "CSV Files (*.csv)")), \
                 patch.object(import_export_mixin.QFileDialog, "getSaveFileName", return_value=(str(export_path), "CSV Files (*.csv)")), \
                 patch.object(import_export_mixin.QMessageBox, "information", return_value=None), \
                 patch.object(import_export_mixin.QMessageBox, "warning", return_value=None), \
                 patch.object(import_export_mixin.QMessageBox, "critical", return_value=None):

                self.window.import_data()
                self.assertEqual(self.window.db["people"].count_documents({}), 2)
                self.assertEqual(self.window.db["people"].find_one({"_id": "1"})["name"], "Ada")

                self.window.export_data()
                self.assertTrue(export_path.exists())
                with export_path.open("r", encoding="utf-8") as f:
                    exported_rows = list(csv.DictReader(f))
                self.assertEqual(len(exported_rows), 2)
                self.assertEqual(exported_rows[0]["name"], "Ada")

    def test_edit_and_delete_user_flow(self):
        user_id = ObjectId("507f1f77bcf86cd799439011")
        self.window.db.create_collection("users_unified")
        self.window.db["users_unified"].insert_one({
            "_id": user_id,
            "nombre": "Ada Lovelace",
            "email": "ada@example.com",
            "role": "admin",
        })

        edit_result = {}

        with patch.object(user_mixin, "QLineEdit", FakeLineEdit), \
             patch.object(user_mixin, "QComboBox", FakeComboBox), \
             patch.object(user_mixin.QDialog, "exec", return_value=QDialog.DialogCode.Accepted), \
             patch.object(user_mixin.QMessageBox, "information", return_value=None), \
             patch.object(user_mixin.QMessageBox, "warning", return_value=None), \
             patch.object(user_mixin.QMessageBox, "critical", return_value=None):

            self.window.edit_user(user_id, "users_unified")
            edit_result = self.window.db["users_unified"].find_one({"_id": user_id})

        self.assertEqual(edit_result["nombre"], "Ada Lovelace")
        self.assertEqual(edit_result["email"], "ada@example.com")
        self.assertEqual(edit_result["role"], "admin")

        with patch.object(user_mixin.QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(user_mixin.QMessageBox, "information", return_value=None), \
             patch.object(user_mixin.QMessageBox, "warning", return_value=None), \
             patch.object(user_mixin.QMessageBox, "critical", return_value=None):

            self.window.delete_user(user_id, "users_unified")

        self.assertIsNone(self.window.db["users_unified"].find_one({"_id": user_id}))

    def test_collection_view_metadata_and_classification(self):
        self.window.db.create_collection("products")
        self.window.db["products"].insert_one({"name": "Monitor", "price": 120, "category": "display"})
        self.window.db.create_collection("logs")
        self.window.db["logs"].insert_one({"event": "login", "message": "ok"})
        self.window.db.create_collection("users")
        self.window.db["users"].insert_one({
            "name": "Ada",
            "email": "ada@example.com",
            "phone": "123",
            "address": "Street 1",
        })
        self.window.db["users"].insert_one({
            "name": "Grace",
            "email": "grace@example.com",
            "role": "admin",
        })
        self.window.db.create_collection("geo")
        self.window.db["geo"].insert_one({"location": {"type": "Point", "coordinates": [1, 2]}})
        self.window.db.create_collection("excel")
        self.window.db["excel"].insert_one({
            "sheet_name": "Sheet1",
            "row": 1,
            "col": 1,
            "header": "A",
            "value": "x",
            "format": "text",
        })

        self.assertEqual(self.window.get_field_description("_id"), "Identificador único del documento")
        self.assertEqual(self.window.get_field_description("correo"), "Correo electrónico")
        self.assertEqual(self.window.get_field_description("fecha_actualizacion"), "Fecha")
        self.assertEqual(self.window.get_field_description("customer_id"), "Identificador único")

        self.assertEqual(self.window.detect_collection_content_type("products"), "Tabla de datos")
        self.assertEqual(self.window.detect_collection_content_type("logs"), "Tabla de datos")
        self.assertEqual(self.window.detect_collection_content_type("users"), "Datos de usuarios")
        self.assertEqual(self.window.detect_collection_content_type("geo"), "Datos geoespaciales")
        self.assertEqual(self.window.detect_collection_content_type("excel"), "Datos de Excel")

        self.window.meta_collection_name = FakeLabel()
        self.window.meta_document_count = FakeLabel()
        self.window.meta_size = FakeLabel()
        self.window.meta_avg_doc_size = FakeLabel()
        self.window.meta_indexes = FakeLabel()
        self.window.meta_index_size = FakeLabel()
        self.window.meta_content_type = FakeLabel()
        self.window.meta_owner_name = FakeLabel()
        self.window.meta_owner_email = FakeLabel()
        self.window.meta_owner_department = FakeLabel()
        self.window.meta_owner_role = FakeLabel()
        self.window.meta_created_date = FakeLabel()
        self.window.meta_modified_date = FakeLabel()
        self.window.meta_fields_table = FakeTable()
        self.window.find_collection_owner = lambda collection_name: {
            "nombre": "Equipo Datos",
            "email": "datos@example.com",
            "departamento": "IT",
            "cargo": "Owner",
        }
        self.window.load_access_history = lambda collection_name: None

        self.window.load_collection_metadata("users")

        self.assertEqual(self.window.meta_collection_name.text_value, "users")
        self.assertEqual(self.window.meta_document_count.text_value, "2")
        self.assertEqual(self.window.meta_content_type.text_value, "Datos de usuarios")
        self.assertEqual(self.window.meta_owner_name.text_value, "Equipo Datos")
        self.assertEqual(self.window.meta_owner_email.text_value, "datos@example.com")
        self.assertEqual(self.window.meta_owner_department.text_value, "IT")
        self.assertEqual(self.window.meta_owner_role.text_value, "Owner")
        self.assertEqual(self.window.meta_fields_table.rows, 4)

    def test_collection_owner_discovery(self):
        self.window.db.create_collection("orders")
        self.window.db["orders"].insert_one({
            "type": "metadata",
            "owner": "Equipo Ventas",
            "email": "ventas@example.com",
            "department": "Sales",
            "role": "Owner",
            "phone": "555-0101",
        })
        self.window.db.create_collection("invoices")
        self.window.db["invoices"].insert_one({
            "created_by": "Equipo Finanzas",
            "email": "finanzas@example.com",
            "department": "Finance",
            "role": "Admin",
        })
        self.window.db.create_collection("users")
        self.window.db["users"].insert_one({
            "name": "User Owner",
            "email": "owner@example.com",
            "department": "IT",
            "role": "owner",
            "permissions": {"collections": "archive", "role": "owner"},
        })
        self.window.db.create_collection("archive")
        self.window.db["archive"].insert_one({"name": "doc"})

        owners = self.window.get_all_collection_owners()

        self.assertEqual(owners["orders"]["nombre"], "Equipo Ventas")
        self.assertEqual(owners["orders"]["email"], "ventas@example.com")
        self.assertEqual(owners["invoices"]["nombre"], "Equipo Finanzas")
        self.assertEqual(owners["archive"]["nombre"], "User Owner")
        self.assertEqual(self.window.find_collection_owner("orders")["cargo"], "Owner")
        self.assertEqual(self.window.find_collection_owner("archive")["email"], "owner@example.com")


if __name__ == "__main__":
    unittest.main()
