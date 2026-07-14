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
    QPlainTextEdit,
    QMessageBox,
    QProgressDialog,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
)


class CollectionViewMixin:
    """Métodos de visualización y navegación de colecciones para MainWindow."""

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

            editor_dialog = QDialog(self)
            editor_dialog.setWindowTitle(f"Editar Registro - {self.current_collection}")
            editor_dialog.resize(800, 600)

            layout = QVBoxLayout(editor_dialog)
            layout.addWidget(QLabel("Edite el documento en formato JSON. El campo _id se mantiene protegido."))

            editor = QPlainTextEdit()
            editor.setPlainText(json_util.dumps(document, indent=2))
            layout.addWidget(editor)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(editor_dialog.accept)
            buttons.rejected.connect(editor_dialog.reject)
            layout.addWidget(buttons)

            if editor_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            try:
                updated_document = json_util.loads(editor.toPlainText())
            except Exception as parse_error:
                QMessageBox.critical(self, "Error", f"El JSON editado no es válido: {str(parse_error)}")
                return

            updated_document["_id"] = document["_id"]

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

            insert_dialog = QDialog(self)
            insert_dialog.setWindowTitle(f"Nuevo Registro - {self.current_collection}")
            insert_dialog.resize(800, 600)

            layout = QVBoxLayout(insert_dialog)
            layout.addWidget(QLabel("Introduzca el documento en formato JSON. Si omite _id, MongoDB lo generará."))

            editor = QPlainTextEdit()
            editor.setPlainText("{\n  \n}")
            layout.addWidget(editor)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(insert_dialog.accept)
            buttons.rejected.connect(insert_dialog.reject)
            layout.addWidget(buttons)

            if insert_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            try:
                new_document = json_util.loads(editor.toPlainText())
            except Exception as parse_error:
                QMessageBox.critical(self, "Error", f"El JSON introducido no es válido: {str(parse_error)}")
                return

            if not isinstance(new_document, dict):
                QMessageBox.warning(self, "Advertencia", "El documento debe ser un objeto JSON")
                return

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
