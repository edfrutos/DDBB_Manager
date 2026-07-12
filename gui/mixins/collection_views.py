import datetime
import traceback
import time

import sip

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QStyle,
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
            if not self.collections_tree or sip.isdeleted(self.collections_tree):
                return False
            if not self.collections_model or sip.isdeleted(self.collections_model):
                return False
            if self._tree_destroyed or not self.collections_tree.isVisible():
                return False
            if not self.collections_model.rowCount():
                return False
            if not self.collections_tree.parent():
                return False
            if not hasattr(self, "_tree_layout") or not self._tree_layout:
                return False
            if self._tree_layout.indexOf(self.collections_tree) == -1:
                return False
            if not self.collections_tree.window():
                return False
            if not self.collections_tree.signalsBlocked():
                return False
            if not self.collections_tree.model():
                return False
            if not self.collections_tree.topLevelItemCount():
                return False
            if not self.collections_tree.selectionModel():
                return False
            if not self.collections_tree.header():
                return False
            if not self.collections_tree.invisibleRootItem():
                return False
            if not self.collections_tree.viewport():
                return False
            if not self.collections_tree.horizontalScrollBar() or not self.collections_tree.verticalScrollBar():
                return False
            if not self.collections_tree.itemDelegate():
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
            if not index.isValid() or not self.db:
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
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load collection data: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al configurar la vista de colección: {str(e)}")
