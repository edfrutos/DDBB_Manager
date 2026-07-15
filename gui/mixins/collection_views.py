import datetime
import traceback
import time

from bson import json_util

try:
    from PyQt6 import sip
except ImportError:
    import sip

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidgetItem,
    QTreeView,
    QVBoxLayout,
)


class CollectionViewMixin:
    """Métodos de visualización y navegación de colecciones para MainWindow."""

    def _document_value_to_text(self, value):
        if isinstance(value, str):
            return value
        try:
            return json_util.dumps(value, default=str)
        except Exception:
            return str(value)

    def _editor_text_to_value(self, text):
        raw_text = text.strip()
        if not raw_text:
            return ""

        try:
            return json_util.loads(raw_text)
        except Exception:
            return raw_text

    def _create_document_editor_dialog(self, title, document=None, allow_id_edit=False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(900, 650)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Edite los campos directamente en la tabla. Puede añadir o quitar filas para crear nuevos campos."))

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Campo", "Valor"])
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        layout.addWidget(table)

        button_row = QHBoxLayout()
        add_field_button = QPushButton("Añadir campo")
        remove_field_button = QPushButton("Eliminar campo")
        button_row.addWidget(add_field_button)
        button_row.addWidget(remove_field_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)

        def add_blank_row(field_name="", value_text=""):
            row = table.rowCount()
            table.insertRow(row)

            field_item = QTableWidgetItem(str(field_name))
            value_item = QTableWidgetItem(value_text)

            if field_name == "_id" and not allow_id_edit:
                field_item.setFlags(field_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 0, field_item)
            table.setItem(row, 1, value_item)

        def populate_rows():
            table.setRowCount(0)
            if document:
                ordered_fields = ["_id"] + [key for key in document.keys() if key != "_id"]
                for field in ordered_fields:
                    add_blank_row(field, self._document_value_to_text(document.get(field, "")))
            else:
                add_blank_row()

        def remove_selected_row():
            selected_row = table.currentRow()
            if selected_row >= 0:
                table.removeRow(selected_row)

        def build_document():
            updated_document = {}
            for row in range(table.rowCount()):
                field_item = table.item(row, 0)
                value_item = table.item(row, 1)
                if field_item is None:
                    continue

                field_name = field_item.text().strip()
                if not field_name:
                    continue

                value_text = value_item.text() if value_item is not None else ""
                if field_name == "_id" and document is not None and not allow_id_edit:
                    updated_document["_id"] = document["_id"]
                    continue

                updated_document[field_name] = self._editor_text_to_value(value_text)

            if document is not None and "_id" in document and "_id" not in updated_document:
                updated_document["_id"] = document["_id"]

            return updated_document

        add_field_button.clicked.connect(lambda: add_blank_row())
        remove_field_button.clicked.connect(remove_selected_row)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        populate_rows()
        return dialog, table, build_document, add_blank_row

    def load_collection_relations(self, collection_name):
        """Populate the relations tab with inferred references to other collections."""
        try:
            if not hasattr(self, "tables_tree") or self.tables_tree is None:
                return

            self.tables_tree.clear()
            self.tables_tree.setHeaderLabels(["Tabla", "Tipo", "Campos"])

            if self.db is None or collection_name not in self.db.list_collection_names():
                return

            source_collection = self.db[collection_name]
            sample_docs = list(source_collection.find().limit(100))
            if not sample_docs:
                empty_item = QTreeWidgetItem(["Sin relaciones detectadas", "Colección vacía", "No hay datos para analizar"])
                self.tables_tree.addTopLevelItem(empty_item)
                self.tables_tree.expandAll()
                return

            other_collections = [name for name in self.db.list_collection_names() if name != collection_name]
            relations = {}

            try:
                from bson.objectid import ObjectId
            except ImportError:
                ObjectId = None

            def candidate_ids(value):
                candidates = []
                if value is None:
                    return candidates
                if ObjectId is not None and isinstance(value, ObjectId):
                    candidates.append(value)
                    candidates.append(str(value))
                    return candidates
                if isinstance(value, str):
                    text = value.strip()
                    if text:
                        candidates.append(text)
                        if ObjectId is not None:
                            try:
                                candidates.append(ObjectId(text))
                            except Exception:
                                pass
                    return candidates
                if isinstance(value, (int, float, bool)):
                    return [value]
                return candidates

            for doc in sample_docs:
                for field, value in doc.items():
                    if field == "_id":
                        continue

                    values = value if isinstance(value, list) else [value]
                    for raw_value in values:
                        for candidate in candidate_ids(raw_value):
                            for related_collection_name in other_collections:
                                related_collection = self.db[related_collection_name]
                                try:
                                    match = related_collection.find_one({"_id": candidate})
                                except Exception:
                                    match = None

                                if match is None and isinstance(candidate, str) and ObjectId is not None:
                                    try:
                                        match = related_collection.find_one({"_id": ObjectId(candidate)})
                                    except Exception:
                                        match = None

                                if match is None:
                                    continue

                                key = (field, related_collection_name)
                                relation = relations.setdefault(
                                    key,
                                    {
                                        "count": 0,
                                        "examples": [],
                                    },
                                )
                                relation["count"] += 1
                                if len(relation["examples"]) < 3:
                                    relation["examples"].append(str(raw_value))
                                break

            if not relations:
                empty_item = QTreeWidgetItem(["Sin relaciones detectadas", "Referencia no encontrada", "No se detectaron vínculos entre colecciones"])
                self.tables_tree.addTopLevelItem(empty_item)
                self.tables_tree.expandAll()
                return

            grouped = {}
            for (field, related_collection_name), info in relations.items():
                grouped.setdefault(related_collection_name, []).append((field, info))

            source_item = QTreeWidgetItem([collection_name, "Origen", f"{len(grouped)} colecciones relacionadas"])
            self.tables_tree.addTopLevelItem(source_item)

            for related_collection_name in sorted(grouped.keys()):
                field_summaries = []
                total_hits = 0
                for field, info in sorted(grouped[related_collection_name], key=lambda item: item[0]):
                    total_hits += info["count"]
                    example_text = ", ".join(info["examples"]) if info["examples"] else "sin ejemplos"
                    field_summaries.append(f"{field}: {info['count']} coincidencias ({example_text})")

                relation_item = QTreeWidgetItem([
                    related_collection_name,
                    "Referencia inferida",
                    " | ".join(field_summaries),
                ])
                source_item.addChild(relation_item)

            self.tables_tree.expandAll()

        except Exception as e:
            print(f"Error al cargar relaciones de colección: {e}")
            traceback.print_exc()

    def show_collections(self):
        """Mostrar las colecciones de la base de datos en el árbol, según el modo de vista activo."""
        if self.db is None:
            return

        try:
            if not self.is_tree_view_valid() and not self.ensure_tree_view_exists():
                print("No se pudo preparar la vista de árbol de colecciones")
                return

            self.collections_model.clear()
            self._model_items.clear()
            self._db_items.clear()
            if hasattr(self, "_collections_refs"):
                self._collections_refs.clear()

            root_item = self.collections_model.invisibleRootItem()
            db_item = QStandardItem(self.database_name)
            db_item.setEditable(False)
            db_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon))

            self._db_items[self.database_name] = db_item
            root_item.appendRow(db_item)

            collections = self.db.list_collection_names()
            total_collections = len(collections)
            print(f"Found {total_collections} collections in database {self.database_name}")

            view_mode = getattr(self, "view_mode", 0)
            if view_mode == 1:
                root_item.removeRow(0)
                self.create_user_grouped_view(self.collections_model, collections)
                return
            if view_mode == 2:
                root_item.removeRow(0)
                self.create_type_grouped_view(self.collections_model, collections)
                return
            if view_mode == 3:
                root_item.removeRow(0)
                self.create_flat_view(self.collections_model, collections)
                return

            progress = None
            if total_collections > 10:
                progress = QProgressDialog("Cargando colecciones...", "Cancelar", 0, total_collections, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(500)

            collection_items_batch = []
            batch_size = 10

            for i, collection_name in enumerate(collections):
                if progress and progress.wasCanceled():
                    break

                try:
                    doc_count = self.db[collection_name].count_documents({})
                except Exception:
                    doc_count = 0

                collection_item = QStandardItem(f"{collection_name} ({doc_count})")
                collection_item.setEditable(False)
                item_id = f"collection_{collection_name}_{i}"
                self._collections_refs[item_id] = collection_item
                self._model_items.append(collection_item)

                if db_item is not None and not sip.isdeleted(db_item):
                    db_item.appendRow(collection_item)
                    collection_items_batch.append(collection_item)
                    if len(collection_items_batch) >= batch_size:
                        QApplication.processEvents()
                        collection_items_batch = []
                else:
                    print(f"Error: db_item no es válido al procesar la colección {collection_name}")

                if progress:
                    progress.setValue(i + 1)

            if progress:
                progress.setValue(total_collections)

            if self.is_tree_view_valid() and self.collections_model.rowCount() > 0:
                self.collections_tree.expandToDepth(0)

        except Exception as e:
            print(f"Error showing collections: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error al obtener las colecciones: {str(e)}")
            if not hasattr(self, "_show_collections_recursion_guard"):
                try:
                    self._show_collections_recursion_guard = True
                    QTimer.singleShot(100, self.reset_and_show_collections)
                except Exception as restart_error:
                    print(f"Error en reinicio: {restart_error}")

    def create_flat_view(self, model, collections):
        """Vista plana: todas las colecciones directamente bajo la raíz, sin agrupar."""
        root_item = model.invisibleRootItem()
        for collection_name in sorted(collections):
            try:
                doc_count = self.db[collection_name].count_documents({})
            except Exception:
                doc_count = 0
            item = QStandardItem(f"{collection_name} ({doc_count})")
            item.setEditable(False)
            self._model_items.append(item)
            root_item.appendRow(item)

        if self.is_tree_view_valid():
            self.collections_tree.expandToDepth(0)

    def create_type_grouped_view(self, model, collections):
        """Vista agrupada por tipo de contenido detectado en cada colección."""
        root_item = model.invisibleRootItem()
        groups = {}
        for collection_name in collections:
            content_type = self.detect_collection_content_type(collection_name)
            groups.setdefault(content_type, []).append(collection_name)

        for content_type in sorted(groups.keys()):
            type_item = QStandardItem(f"{content_type} ({len(groups[content_type])})")
            type_item.setEditable(False)
            type_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            self._model_items.append(type_item)
            root_item.appendRow(type_item)

            for collection_name in sorted(groups[content_type]):
                try:
                    doc_count = self.db[collection_name].count_documents({})
                except Exception:
                    doc_count = 0
                item = QStandardItem(f"{collection_name} ({doc_count})")
                item.setEditable(False)
                self._model_items.append(item)
                type_item.appendRow(item)

        if self.is_tree_view_valid():
            self.collections_tree.expandToDepth(0)

    def create_user_grouped_view(self, model, collections):
        """Vista agrupada por propietario de cada colección."""
        root_item = model.invisibleRootItem()
        groups = {}
        for collection_name in collections:
            owner_info = self.find_collection_owner(collection_name)
            owner_name = owner_info.get("nombre", "Desconocido") if owner_info else "Desconocido"
            groups.setdefault(owner_name, []).append(collection_name)

        for owner_name in sorted(groups.keys()):
            owner_item = QStandardItem(f"{owner_name} ({len(groups[owner_name])})")
            owner_item.setEditable(False)
            owner_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon))
            self._model_items.append(owner_item)
            root_item.appendRow(owner_item)

            for collection_name in sorted(groups[owner_name]):
                try:
                    doc_count = self.db[collection_name].count_documents({})
                except Exception:
                    doc_count = 0
                item = QStandardItem(f"{collection_name} ({doc_count})")
                item.setEditable(False)
                self._model_items.append(item)
                owner_item.appendRow(item)

        if self.is_tree_view_valid():
            self.collections_tree.expandToDepth(0)

    def reset_and_show_collections(self):
        try:
            if hasattr(self, "_show_collections_recursion_guard"):
                delattr(self, "_show_collections_recursion_guard")

            if hasattr(self, "collections_model") and self.collections_model:
                self.collections_model.clear()

            self._model_items.clear()
            self._db_items.clear()

            if hasattr(self, "_collections_refs"):
                self._collections_refs.clear()

            self.ensure_tree_view_exists()
            self.show_collections()
        except Exception as e:
            print(f"Error reiniciando vista de colecciones: {e}")
            QMessageBox.critical(self, "Error", f"Error al reiniciar la vista de colecciones: {str(e)}")

    def is_tree_view_valid(self):
        """Verifica si la vista de árbol de colecciones existe y es válida."""
        if not self._widget_safe_access:
            return False

        try:
            if self.collections_tree is None or sip.isdeleted(self.collections_tree):
                return False
            if self.collections_model is None or sip.isdeleted(self.collections_model):
                return False
            if self._tree_destroyed:
                return False
            if self.collections_tree.parent() is None:
                return False
            if not hasattr(self, "_tree_layout") or self._tree_layout is None:
                return False
            if self._tree_layout.indexOf(self.collections_tree) == -1:
                return False
            if self.collections_tree.window() is None:
                return False
            if self.collections_tree.model() is None:
                return False
            if self.collections_tree.selectionModel() is None:
                return False
            if self.collections_tree.header() is None:
                return False
            if self.collections_tree.viewport() is None:
                return False
            if self.collections_tree.horizontalScrollBar() is None or self.collections_tree.verticalScrollBar() is None:
                return False
            if self.collections_tree.itemDelegate() is None:
                return False
            return True
        except Exception:
            return False

    def ensure_tree_view_exists(self):
        """Ensure the collections tree view exists and is valid, recreate if needed."""
        current_time = time.time()
        if not hasattr(self, "_last_tree_recreation_time") or current_time - self._last_tree_recreation_time > 60:
            self._tree_recreation_attempts = 0
        self._last_tree_recreation_time = current_time
        self._tree_recreation_attempts += 1

        if self._tree_recreation_attempts >= 3:
            print("Maximum tree view recreation attempts (3) reached")
            return False

        if not hasattr(self, "tree_widget") or self.tree_widget is None or sip.isdeleted(self.tree_widget):
            print("Tree widget container is missing or invalid, cannot recreate tree view")
            return False

        tree_layout = getattr(self, "_tree_layout", None)
        if not tree_layout or sip.isdeleted(tree_layout):
            try:
                tree_layout = self.tree_widget.layout()
            except Exception:
                tree_layout = None
            if not tree_layout:
                print("Tree widget has no layout, cannot recreate tree view")
                return False
            self._tree_layout = tree_layout

        if hasattr(self, "collections_tree") and self.collections_tree and not sip.isdeleted(self.collections_tree):
            try:
                try:
                    self.collections_tree.doubleClicked.disconnect()
                except Exception:
                    pass
                tree_layout.removeWidget(self.collections_tree)
                self.collections_tree.setModel(None)
                self.collections_tree.deleteLater()
            except Exception as cleanup_error:
                print(f"Error during tree view cleanup: {cleanup_error}")
                traceback.print_exc()

        self._model_items.clear()
        self._db_items.clear()
        if hasattr(self, "_collections_refs"):
            self._collections_refs.clear()
        else:
            self._collections_refs = {}

        if not hasattr(self, "collections_model") or self.collections_model is None:
            self.collections_model = QStandardItemModel()
        else:
            self.collections_model.clear()

        QApplication.processEvents()

        try:
            self.collections_tree = QTreeView(self.tree_widget)
            self.collections_tree.setHeaderHidden(True)
            self.collections_tree.setMinimumWidth(250)
            self.collections_tree.setObjectName("collectionsTreeView")
            self.collections_tree.setModel(self.collections_model)
            tree_layout.addWidget(self.collections_tree)
            self.collections_tree.clicked.connect(self.view_collection_data)
            self.collections_tree.doubleClicked.connect(self.view_collection_data)
            self._tree_destroyed = False
            return True
        except Exception as e:
            print(f"Error recreating collections tree: {e}")
            traceback.print_exc()
            return False

    def view_collection_data(self, index):
        """Handle double-click event on collections tree to view collection data."""
        try:
            if not index.isValid() or self.db is None:
                return

            model = index.model()
            if not model:
                return

            item = model.itemFromIndex(index)
            if not item:
                return

            item_text = item.text()
            collection_name = item_text.split(" (")[0] if " (" in item_text else item_text

            if collection_name not in self.db.list_collection_names():
                print(f"Collection {collection_name} not found")
                return

            self.current_collection = collection_name
            self.show_collection_data(collection_name, limit=100, with_metadata=True)

            if hasattr(self, "collection_view_tabs"):
                self.collection_view_tabs.setCurrentIndex(0)

            self.show_status_message(f"Mostrando datos de {collection_name}")
        except Exception as e:
            print(f"Error viewing collection data: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error al mostrar datos de colección: {str(e)}")

    def edit_selected_document(self):
        """Editar el documento seleccionado en la tabla de datos de la colección actual."""
        try:
            if self.db is None:
                QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
                return

            if not getattr(self, "current_collection", None):
                QMessageBox.warning(self, "Advertencia", "Seleccione una colección primero")
                return

            if not hasattr(self, "data_table") or self.data_table is None:
                QMessageBox.warning(self, "Advertencia", "No hay datos cargados para editar")
                return

            selected_items = self.data_table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "Advertencia", "Seleccione un registro para editar")
                return

            selected_row = self.data_table.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self, "Advertencia", "Seleccione un registro para editar")
                return

            if self.data_table.columnCount() == 0:
                QMessageBox.warning(self, "Advertencia", "La tabla no contiene datos editables")
                return

            id_item = self.data_table.item(selected_row, 0)
            if id_item is None:
                QMessageBox.warning(self, "Advertencia", "No se pudo identificar el documento seleccionado")
                return

            raw_id = id_item.text().strip()
            if not raw_id:
                QMessageBox.warning(self, "Advertencia", "No se pudo identificar el documento seleccionado")
                return

            collection = self.db[self.current_collection]
            document = collection.find_one({"_id": raw_id})
            if document is None:
                try:
                    from bson.objectid import ObjectId
                    document = collection.find_one({"_id": ObjectId(raw_id)})
                except Exception:
                    document = None

            if document is None:
                QMessageBox.warning(self, "Advertencia", "No se encontró el documento seleccionado en la base de datos")
                return

            editor_dialog, editor_table, build_document, _add_row = self._create_document_editor_dialog(
                f"Editar Registro - {self.current_collection}",
                document=document,
                allow_id_edit=False,
            )

            if editor_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            try:
                updated_document = build_document()
            except Exception as parse_error:
                QMessageBox.critical(self, "Error", f"No se pudo leer el documento editado: {str(parse_error)}")
                return

            try:
                result = collection.replace_one({"_id": document["_id"]}, updated_document)
            except Exception as update_error:
                QMessageBox.critical(self, "Error", f"No se pudo guardar el registro: {str(update_error)}")
                return

            if getattr(result, "matched_count", 0) == 0:
                QMessageBox.warning(self, "Advertencia", "No se encontró el documento para actualizar")
                return

            self.show_collection_data(self.current_collection, limit=100, with_metadata=True)
            self.show_status_message(f"Registro actualizado en '{self.current_collection}'")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al editar el registro: {str(e)}")
            traceback.print_exc()

    def delete_selected_document(self):
        """Eliminar el documento seleccionado en la tabla de datos de la colección actual."""
        try:
            if self.db is None:
                QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
                return

            if not getattr(self, "current_collection", None):
                QMessageBox.warning(self, "Advertencia", "Seleccione una colección primero")
                return

            if not hasattr(self, "data_table") or self.data_table is None:
                QMessageBox.warning(self, "Advertencia", "No hay datos cargados para eliminar")
                return

            selected_row = self.data_table.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self, "Advertencia", "Seleccione un registro para eliminar")
                return

            id_item = self.data_table.item(selected_row, 0)
            if id_item is None or not id_item.text().strip():
                QMessageBox.warning(self, "Advertencia", "No se pudo identificar el documento seleccionado")
                return

            raw_id = id_item.text().strip()
            collection = self.db[self.current_collection]
            document = collection.find_one({"_id": raw_id})
            if document is None:
                try:
                    from bson.objectid import ObjectId
                    document = collection.find_one({"_id": ObjectId(raw_id)})
                except Exception:
                    document = None

            if document is None:
                QMessageBox.warning(self, "Advertencia", "No se encontró el documento seleccionado en la base de datos")
                return

            confirm = QMessageBox.question(
                self,
                "Confirmar Eliminación",
                "¿Está seguro de que desea eliminar el registro seleccionado?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            result = collection.delete_one({"_id": document["_id"]})
            if getattr(result, "deleted_count", 0) == 0:
                QMessageBox.warning(self, "Advertencia", "No se pudo eliminar el documento seleccionado")
                return

            self.show_collection_data(self.current_collection, limit=100, with_metadata=True)
            self.show_status_message(f"Registro eliminado de '{self.current_collection}'")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al eliminar el registro: {str(e)}")
            traceback.print_exc()

    def insert_new_document(self):
        """Crear un nuevo documento en la colección actual desde un editor JSON."""
        try:
            if self.db is None:
                QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
                return

            if not getattr(self, "current_collection", None):
                QMessageBox.warning(self, "Advertencia", "Seleccione una colección primero")
                return

            insert_dialog, editor_table, build_document, add_row = self._create_document_editor_dialog(
                f"Nuevo Registro - {self.current_collection}",
                document=None,
                allow_id_edit=True,
            )

            if insert_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            try:
                new_document = build_document()
            except Exception as parse_error:
                QMessageBox.critical(self, "Error", f"No se pudo leer el documento nuevo: {str(parse_error)}")
                return

            if not isinstance(new_document, dict):
                QMessageBox.warning(self, "Advertencia", "El documento debe contener campos válidos")
                return

            new_document.pop("_id", None)

            collection = self.db[self.current_collection]
            try:
                result = collection.insert_one(new_document)
            except Exception as insert_error:
                QMessageBox.critical(self, "Error", f"No se pudo crear el registro: {str(insert_error)}")
                return

            self.show_collection_data(self.current_collection, limit=100, with_metadata=True)
            self.show_status_message(f"Registro creado en '{self.current_collection}' ({result.inserted_id})")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al crear el registro: {str(e)}")
            traceback.print_exc()

    def duplicate_selected_document(self):
        """Duplicar el documento seleccionado en la tabla de datos de la colección actual."""
        try:
            if self.db is None:
                QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
                return

            if not getattr(self, "current_collection", None):
                QMessageBox.warning(self, "Advertencia", "Seleccione una colección primero")
                return

            if not hasattr(self, "data_table") or self.data_table is None:
                QMessageBox.warning(self, "Advertencia", "No hay datos cargados para duplicar")
                return

            selected_row = self.data_table.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self, "Advertencia", "Seleccione un registro para duplicar")
                return

            id_item = self.data_table.item(selected_row, 0)
            if id_item is None or not id_item.text().strip():
                QMessageBox.warning(self, "Advertencia", "No se pudo identificar el documento seleccionado")
                return

            raw_id = id_item.text().strip()
            collection = self.db[self.current_collection]
            document = collection.find_one({"_id": raw_id})
            if document is None:
                try:
                    from bson.objectid import ObjectId
                    document = collection.find_one({"_id": ObjectId(raw_id)})
                except Exception:
                    document = None

            if document is None:
                QMessageBox.warning(self, "Advertencia", "No se encontró el documento seleccionado en la base de datos")
                return

            duplicate_document = json_util.loads(json_util.dumps(document))
            duplicate_document.pop("_id", None)

            try:
                result = collection.insert_one(duplicate_document)
            except Exception as insert_error:
                QMessageBox.critical(self, "Error", f"No se pudo duplicar el registro: {str(insert_error)}")
                return

            self.show_collection_data(self.current_collection, limit=100, with_metadata=True)
            self.show_status_message(f"Registro duplicado en '{self.current_collection}' ({result.inserted_id})")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al duplicar el registro: {str(e)}")
            traceback.print_exc()

    def show_collection_data(self, collection_name, limit=100, with_metadata=False):
        """Show data from the specified collection in the data table."""
        try:
            if self.db is None:
                return

            collection = self.db[collection_name]
            documents_list = list(collection.find().limit(limit))

            if hasattr(self, "data_table") and self.data_table is not None:
                self.data_table.clear()
                self.data_table.setRowCount(0)
                self.data_table.setColumnCount(0)
                self.data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
                self.data_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
                if self.data_table.parent() is None and hasattr(self, "collections_tab_widget"):
                    data_tab = self.collections_tab_widget.widget(0)
                    if data_tab and data_tab.layout():
                        data_tab.layout().addWidget(self.data_table)

            if not documents_list:
                self.show_status_message(f"Collection '{collection_name}' is empty")
                self.load_collection_relations(collection_name)
                if with_metadata:
                    self.load_collection_metadata(collection_name)
                return

            all_fields = set()
            for doc in documents_list:
                all_fields.update(doc.keys())

            if "_id" in all_fields:
                all_fields.remove("_id")

            field_list = ["_id"] + sorted(list(all_fields))

            try:
                self.data_table.setColumnCount(len(field_list))
                self.data_table.setHorizontalHeaderLabels(field_list)
                for row_idx, doc in enumerate(documents_list):
                    self.data_table.insertRow(row_idx)
                    for col_idx, field in enumerate(field_list):
                        if field in doc:
                            item = QTableWidgetItem(str(doc[field]))
                            self.data_table.setItem(row_idx, col_idx, item)

                self.data_table.resizeColumnsToContents()
                total_docs = collection.count_documents({})
                self.show_status_message(f"Showing {min(limit, total_docs)} of {total_docs} documents in '{collection_name}'")

                self.load_collection_relations(collection_name)

                if with_metadata:
                    self.load_collection_metadata(collection_name)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load collection data: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al configurar la vista de colección: {str(e)}")

    def load_collection_metadata(self, collection_name):
        """Load collection metadata into the metadata panel."""
        try:
            if not hasattr(self, "meta_collection_name"):
                return

            collection = self.db[collection_name]

            self.meta_collection_name.setText(collection_name)

            doc_count = collection.count_documents({})
            self.meta_document_count.setText(str(doc_count))

            try:
                stats = self.db.command("collStats", collection_name)
                size_mb = stats.get("size", 0) / (1024 * 1024)
                self.meta_size.setText(f"{size_mb:.2f} MB")

                avg_size_kb = stats.get("avgObjSize", 0) / 1024
                self.meta_avg_doc_size.setText(f"{avg_size_kb:.2f} KB")

                index_count = len(list(collection.list_indexes()))
                self.meta_indexes.setText(str(index_count))

                index_size_mb = stats.get("totalIndexSize", 0) / (1024 * 1024)
                self.meta_index_size.setText(f"{index_size_mb:.2f} MB")
            except Exception as stats_error:
                print(f"Error al obtener estadísticas: {stats_error}")

            content_type = self.detect_collection_content_type(collection_name)
            self.meta_content_type.setText(content_type)

            owner_info = self.find_collection_owner(collection_name)
            self.meta_owner_name.setText(owner_info.get("nombre", "Desconocido"))
            self.meta_owner_email.setText(owner_info.get("email", "N/A"))
            self.meta_owner_department.setText(owner_info.get("departamento", "N/A"))
            self.meta_owner_role.setText(owner_info.get("cargo", "N/A"))

            try:
                first_doc = collection.find_one({}, sort=[("_id", 1)])
                if first_doc and "_id" in first_doc:
                    try:
                        from bson.objectid import ObjectId
                        if isinstance(first_doc["_id"], ObjectId):
                            created_date = first_doc["_id"].generation_time
                            self.meta_created_date.setText(created_date.strftime("%d/%m/%Y %H:%M"))
                        else:
                            self.meta_created_date.setText("N/A (ID no es ObjectId)")
                    except Exception:
                        self.meta_created_date.setText("N/A")
                else:
                    self.meta_created_date.setText("N/A (colección vacía)")

                last_doc = collection.find_one({}, sort=[("_id", -1)])
                if last_doc and "_id" in last_doc:
                    try:
                        from bson.objectid import ObjectId
                        if isinstance(last_doc["_id"], ObjectId):
                            modified_date = last_doc["_id"].generation_time
                            self.meta_modified_date.setText(modified_date.strftime("%d/%m/%Y %H:%M"))
                        else:
                            self.meta_modified_date.setText("N/A (ID no es ObjectId)")
                    except Exception:
                        self.meta_modified_date.setText("N/A")
                else:
                    self.meta_modified_date.setText("N/A (colección vacía)")
            except Exception as date_error:
                print(f"Error al obtener fechas: {date_error}")
                self.meta_created_date.setText("N/A")
                self.meta_modified_date.setText("N/A")

            self.meta_fields_table.setRowCount(0)
            if doc_count > 0:
                sample_doc = collection.find_one()
                if sample_doc:
                    field_infos = []
                    for field, value in sample_doc.items():
                        field_infos.append((field, type(value).__name__, self.get_field_description(field)))

                    field_infos.sort(key=lambda x: x[0])
                    self.meta_fields_table.setRowCount(len(field_infos))
                    for i, (field, field_type, description) in enumerate(field_infos):
                        self.meta_fields_table.setItem(i, 0, QTableWidgetItem(field))
                        self.meta_fields_table.setItem(i, 1, QTableWidgetItem(field_type))
                        self.meta_fields_table.setItem(i, 2, QTableWidgetItem(description))
                    self.meta_fields_table.resizeColumnsToContents()

            self.load_access_history(collection_name)
        except Exception as e:
            print(f"Error al cargar metadatos: {e}")

    def detect_collection_content_type(self, collection_name):
        """Detect the type of content in a collection from its structure."""
        try:
            collection = self.db[collection_name]
            doc_count = collection.count_documents({})
            if doc_count == 0:
                return "Colección vacía"

            sample_docs = list(collection.find().limit(10))
            if not sample_docs:
                return "Desconocido"

            field_types = {}
            data_rows_count = 0
            has_table_structure = True
            has_geospatial_data = False
            has_complex_objects = False
            excel_fields = ["sheet_name", "row", "col", "header", "value", "format"]
            excel_match_count = 0

            text_index = False
            for idx in collection.list_indexes():
                for field, type_val in idx.get("key", {}).items():
                    if type_val == "text":
                        text_index = True
                        break

            for doc in sample_docs:
                if data_rows_count == 0:
                    first_doc_fields = set(doc.keys())
                elif set(doc.keys()) != first_doc_fields:
                    has_table_structure = False

                excel_fields_found = sum(1 for field in excel_fields if field in doc)
                if excel_fields_found >= 3:
                    excel_match_count += 1

                for field, value in doc.items():
                    field_type = type(value).__name__
                    field_types.setdefault(field, set()).add(field_type)
                    if field in ["location", "coordinates", "geometry"] and isinstance(value, dict):
                        if "type" in value and "coordinates" in value:
                            has_geospatial_data = True
                    if isinstance(value, dict) and len(value) > 3:
                        has_complex_objects = True

                data_rows_count += 1

            if excel_match_count >= min(3, len(sample_docs)):
                return "Datos de Excel"
            if text_index:
                return "Documentos de texto"
            if has_geospatial_data:
                return "Datos geoespaciales"
            if has_table_structure and not has_complex_objects:
                return "Tabla de datos"
            if collection_name.lower() in ["users", "usuarios", "clientes", "customers"]:
                return "Datos de usuarios"
            if collection_name.lower() in ["products", "productos", "inventory", "inventario"]:
                return "Catálogo de productos"
            if collection_name.lower() in ["logs", "audit", "eventos", "events"]:
                return "Registros de eventos"
            if has_complex_objects:
                return "Documentos complejos"
            return "Documentos estándar"
        except Exception as e:
            print(f"Error al detectar tipo de contenido: {e}")
            return "Desconocido"

    def get_field_description(self, field_name):
        """Proporciona una descripción para campos comunes."""
        field_lower = field_name.lower()

        if field_name == "_id":
            return "Identificador único del documento"
        if "id" in field_lower or "uuid" in field_lower:
            return "Identificador único"
        if field_lower in ["name", "nombre"]:
            return "Nombre"
        if field_lower in ["email", "correo", "mail"]:
            return "Correo electrónico"
        if field_lower in ["phone", "telefono", "tel", "movil"]:
            return "Número de teléfono"
        if field_lower in ["address", "direccion"]:
            return "Dirección postal"
        if field_lower in ["password", "contrasena", "clave"]:
            return "Contraseña (cifrada)"
        if field_lower in ["role", "rol"]:
            return "Rol o nivel de permisos"
        if field_lower in ["location", "ubicacion", "coordinates", "coordenadas"]:
            return "Datos de ubicación geográfica"
        if "date" in field_lower or "fecha" in field_lower:
            return "Fecha"
        if "time" in field_lower or "hora" in field_lower:
            return "Hora"
        if field_lower in ["created_at", "fecha_creacion", "creation_date"]:
            return "Fecha de creación"
        if field_lower in ["updated_at", "fecha_actualizacion", "last_modified"]:
            return "Fecha de última modificación"
        if field_lower in ["price", "precio"]:
            return "Precio"
        if field_lower in ["cost", "costo"]:
            return "Costo"
        if field_lower in ["description", "descripcion"]:
            return "Descripción"
        if field_lower in ["category", "categoria"]:
            return "Categoría"
        if field_lower in ["stock", "inventory", "inventario"]:
            return "Cantidad en inventario"
        if field_lower in ["type", "tipo"]:
            return "Tipo de documento"
        if field_lower in ["status", "estado"]:
            return "Estado"
        if field_lower in ["tags", "etiquetas"]:
            return "Etiquetas o categorías"
        if field_lower in ["active", "activo"]:
            return "Estado de activación"
        if field_lower in ["comments", "comentarios"]:
            return "Comentarios"
        if field_lower in ["image", "imagen", "photo", "foto"]:
            return "Ruta de imagen o datos binarios"
        if field_lower.endswith("_id"):
            related_entity = field_lower[:-3].replace("_", " ")
            return f"Referencia a {related_entity}"
        return "Campo de datos"
