import sys
import os
import traceback
import time
import datetime
import json
import gzip
import threading
from os import environ
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QTabWidget, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QStatusBar, QMessageBox,
    QMenu, QMenuBar, QDialog, QLineEdit, QFormLayout, QDialogButtonBox,
    QComboBox, QTableWidget, QTableWidgetItem, QSplitter, QTreeView,
    QTreeWidget, QTextEdit, QToolBar, QStyle, QListWidget, QListWidgetItem, QCheckBox, QFrame,
    QProgressDialog, QGroupBox, QFileDialog, QRadioButton, QButtonGroup,
    QStackedWidget, QTimeEdit, QScrollArea, QLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QTimer, QTime, QDateTime, QDate
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont, QIcon, QAction
from .dialogs import (
    CreateCollectionDialog,
    DropCollectionDialog,
    ImportDialog,
    ExportDialog,
    PasswordManageDialog,
    CollectionSelectDialog,
)
from .mixins import MaintenanceMixin, BackupMixin, UserManagementMixin, ImportExportMixin

# Import sip for handling deleted C++ objects
try:
    from PyQt6 import sip
except ImportError:
    try:
        import sip
    except ImportError:
        print("Warning: sip module not found, widget deletion detection will be limited")

# MongoDB imports
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    from bson.objectid import ObjectId
except ImportError:
    print("PyMongo is required. Install it using: pip install pymongo")
    sys.exit(1)
class ConnectionDialog(QDialog):
    """Diálogo de conexión a MongoDB.

    Flujo de dos pasos:
      1. El usuario introduce (o selecciona de un perfil) la URI y pulsa Conectar.
      2. El combo de bases de datos se rellena con list_database_names(); el usuario
         elige una y pulsa OK.

    Perfiles persistidos en ~/.mongodb_manager/connections.json.
    Interfaz pública: get_connection_data() → {"connection_string": ..., "database": ...}
    """

    PROFILES_FILE = os.path.join(
        os.path.expanduser("~"), ".mongodb_manager", "connections.json"
    )

    def __init__(self, parent=None, connection_string=""):
        super().__init__(parent)
        self.setWindowTitle("Conectar a MongoDB")
        self.resize(540, 240)
        self._client = None
        self._profiles = self._load_profiles()

        layout = QVBoxLayout(self)

        # ── Perfil guardado ──────────────────────────────────────────
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Perfil:"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("(nuevo / sin guardar)")
        for p in self._profiles:
            self.profile_combo.addItem(p["name"], p["uri"])
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        profile_row.addWidget(self.profile_combo, 1)
        layout.addLayout(profile_row)

        # ── URI ──────────────────────────────────────────────────────
        form = QFormLayout()
        self.connection_input = QLineEdit()
        self.connection_input.setText(connection_string or "mongodb://localhost:27017/")
        self.connection_input.setPlaceholderText(
            "mongodb://usuario:contraseña@host:puerto/"
        )
        form.addRow("URI:", self.connection_input)
        layout.addLayout(form)

        # ── Conectar + nombre de perfil opcional ─────────────────────
        connect_row = QHBoxLayout()
        self.connect_btn = QPushButton("Conectar")
        self.connect_btn.clicked.connect(self._do_connect)
        connect_row.addWidget(self.connect_btn)
        connect_row.addWidget(QLabel("Guardar como:"))
        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText("Nombre del perfil (opcional)")
        connect_row.addWidget(self.profile_name_input, 1)
        layout.addLayout(connect_row)

        # ── Selector de base de datos (deshabilitado hasta conectar) ─
        db_form = QFormLayout()
        self.db_combo = QComboBox()
        self.db_combo.setEnabled(False)
        db_form.addRow("Base de datos:", self.db_combo)
        layout.addLayout(db_form)

        # ── Botones OK / Cancelar ────────────────────────────────────
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setEnabled(False)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Autoconectar si ya hay URI previa
        if connection_string:
            self._do_connect()

    # ── Perfiles ──────────────────────────────────────────────────────

    def _load_profiles(self):
        try:
            if os.path.exists(self.PROFILES_FILE):
                with open(self.PROFILES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_profile(self, name, uri):
        profiles = self._load_profiles()
        for p in profiles:
            if p["name"] == name:
                p["uri"] = uri
                break
        else:
            profiles.append({"name": name, "uri": uri})
        os.makedirs(os.path.dirname(self.PROFILES_FILE), exist_ok=True)
        with open(self.PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)

    def _on_profile_selected(self, index):
        if index > 0:
            uri = self.profile_combo.itemData(index)
            if uri:
                self.connection_input.setText(uri)

    # ── Conexión ──────────────────────────────────────────────────────

    def _do_connect(self):
        uri = self.connection_input.text().strip()
        if not uri:
            QMessageBox.warning(self, "Advertencia", "Introduce una URI de conexión.")
            return

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Conectando…")
        QApplication.processEvents()

        try:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            self._client = client

            databases = client.list_database_names()
            self.db_combo.clear()
            self.db_combo.addItems(databases)
            self.db_combo.setEnabled(True)
            self._ok_btn.setEnabled(True)
            self.connect_btn.setText("Reconectar")

            profile_name = self.profile_name_input.text().strip()
            if profile_name:
                self._save_profile(profile_name, uri)

        except Exception as exc:
            QMessageBox.critical(
                self, "Error de conexión", f"No se pudo conectar:\n{exc}"
            )
            self.connect_btn.setText("Conectar")
        finally:
            self.connect_btn.setEnabled(True)

    def _on_accept(self):
        if not self._client or not self.db_combo.isEnabled():
            QMessageBox.warning(self, "Sin conexión", "Conecta primero antes de aceptar.")
            return
        self.accept()

    def get_connection_data(self):
        return {
            "connection_string": self.connection_input.text().strip(),
            "database": self.db_combo.currentText(),
        }

    def closeEvent(self, event):
        if self._client and self.result() != QDialog.DialogCode.Accepted:
            try:
                self._client.close()
            except Exception:
                pass
        super().closeEvent(event)
class MainWindow(MaintenanceMixin, BackupMixin, UserManagementMixin, ImportExportMixin, QMainWindow):
    """Main application window for MongoDB database management"""
    
    connection_status_changed = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        # Inicializar variables
        self.client = None
        self.db = None
        self.current_collection = None
        self.connection_in_progress = False  # Bandera para controlar el estado de la conexión
        
        # Initialize UI elements that might be accessed before their creation methods are called
        self.data_table = None
        self.collections_tree = None
        self.tree_widget = None
        self.collections_model = None
        self._tree_layout = None   # Store the tree layout for easier widget recreation
        self._tree_recreation_attempts = 0  # Track how many times we've tried to recreate the tree
        self._widget_safe_access = True  # Flag to control safe widget access
        self._model_items = []  # Keep references to model items to prevent garbage collection
        self._db_items = {}  # Additional container for root database items
        self._collections_refs = {}  # Dictionary to keep strong references to collection items by id
        self._last_tree_recreation_time = time.time()  # Track when we last recreated the tree
        self._tree_destroyed = False  # Flag to track if the tree was destroyed
        
        # Initialize caches for collection data
        self.collection_types_cache = {}  # Cache for collection content types
        self.collection_owners_cache = {}  # Cache for collection owners
        
        # Track widget validity
        self._widgets_initialized = False

        # Modo de vista del árbol de colecciones: 0=jerárquica, 1=por propietario, 2=por tipo, 3=plana
        self.view_mode = 0
        
        # Try to get connection string from environment variables
        self.connection_string = os.environ.get("MONGODB_URI", "")
        print(f"Initial connection string: {'Found (length: ' + str(len(self.connection_string)) + ')' if self.connection_string else 'Not found'}")
        self.database_name = "app_catalogojoyero"

        # Construir la interfaz de usuario
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.setup_dashboard_tab()
        self.setup_collections_tab()
        self.setup_query_tab()
        self.setup_menu_bar()

        self.connection_status_label = QLabel("No conectado")
        self.connection_status_label.setStyleSheet("color: red; padding: 3px;")
        self.statusBar().addPermanentWidget(self.connection_status_label)

        self.connection_status_changed.connect(self.update_connection_status)

        # Deshabilitar pestañas que requieren conexión hasta que se establezca
        self.tab_widget.setTabEnabled(1, False)  # Colecciones

        self.setWindowTitle("Gestor de Base de Datos MongoDB")
        self.resize(1000, 700)

    def setup_dashboard_tab(self):
        """Configurar la pestaña de panel de control"""
        # Crear widget contenedor
        dashboard_widget = QWidget()
        layout = QVBoxLayout(dashboard_widget)
        
        # Información de bienvenida
        info_text = QLabel("""
Este gestor le permite:
• Conectar a bases de datos MongoDB
• Ver y gestionar colecciones
• Ejecutar consultas MongoDB
• Importar y exportar datos

Para comenzar, utilice el menú 'Conexión' para conectarse a una base de datos.
        """)
        layout.addWidget(info_text)
        
        # Sección de estadísticas de la base de datos
        stats_group = QWidget()
        stats_layout = QVBoxLayout(stats_group)
        
        stats_header = QLabel("Estadísticas de la Base de Datos")
        stats_header.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        stats_layout.addWidget(stats_header)
        
        self.stats_content = QTextEdit()
        self.stats_content.setReadOnly(True)
        self.stats_content.setText("Conecte a una base de datos para ver estadísticas")
        self.stats_content.setMinimumHeight(150)
        stats_layout.addWidget(self.stats_content)
        
        layout.addWidget(stats_group)
        
        # Botones de acción rápida
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        
        refresh_button = QPushButton("Actualizar Estadísticas")
        refresh_button.clicked.connect(self.update_database_stats)
        buttons_layout.addWidget(refresh_button)
        
        connect_button = QPushButton("Conectar a MongoDB")
        connect_button.clicked.connect(self.open_connection_dialog)
        buttons_layout.addWidget(connect_button)
        
        layout.addWidget(buttons_widget)
        
        # Agregar espacio flexible al final
        layout.addStretch()
        
        # Agregar la pestaña al widget de pestañas
        self.tab_widget.addTab(dashboard_widget, "Panel de Control")

    def setup_collections_tab(self):
        """Configurar la pestaña de colecciones"""
        # Crear widget contenedor
        collections_widget = QWidget()
        layout = QHBoxLayout(collections_widget)
        
        # Crear un splitter para dividir la vista
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo: árbol de colecciones
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Crear widget para el árbol
        self.tree_widget = QWidget()
        tree_layout = QVBoxLayout(self.tree_widget)
        
        tree_label = QLabel("Colecciones en la Base de Datos:")
        tree_layout.addWidget(tree_label)
        
        # Create the collections tree view with proper parenting
        self.collections_tree = QTreeView(self.tree_widget)
        self.collections_tree.setHeaderHidden(True)
        self.collections_tree.setMinimumWidth(250)
        self.collections_tree.setObjectName("collectionsTreeView")
        tree_layout.addWidget(self.collections_tree)
        
        # Store reference to the layout for recreation if needed
        self._tree_layout = tree_layout
        self._tree_destroyed = False
        
        # Connect signals right after creation to ensure widget isn't deleted
        try:
            if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
                self.collections_tree.doubleClicked.connect(self.view_collection_data)
                print("Collections tree signals connected during initial setup")
            else:
                print("Warning: Collections tree is not valid during setup")
        except Exception as e:
            print(f"Error connecting collections tree signals during setup: {str(e)}")
            
        collections_buttons = QWidget()
        collections_button_layout = QHBoxLayout(collections_buttons)
        
        create_button = QPushButton("Crear")
        create_button.clicked.connect(self.create_collection)
        collections_button_layout.addWidget(create_button)
        
        drop_button = QPushButton("Eliminar")
        drop_button.clicked.connect(self.drop_collection)
        collections_button_layout.addWidget(drop_button)
        
        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self.show_collections)
        collections_button_layout.addWidget(refresh_button)
        
        # Añadir botón para ver propietarios de colecciones
        owner_button = QPushButton("Propietarios")
        owner_button.clicked.connect(self.show_collection_owners)
        owner_button.setToolTip("Ver propietarios de las colecciones")
        collections_button_layout.addWidget(owner_button)
        
        tree_layout.addWidget(collections_buttons)
        
        left_layout.addWidget(self.tree_widget)
        
        # Panel derecho: visualización de datos
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Panel de información general
        info_panel = QWidget()
        info_layout = QVBoxLayout(info_panel)
        
        self.collection_info_label = QLabel("Seleccione una colección para ver sus detalles")
        self.collection_info_label.setWordWrap(True)
        info_layout.addWidget(self.collection_info_label)
        
        info_panel.setLayout(info_layout)
        right_layout.addWidget(info_panel, 1)  # 20% del espacio vertical
        
        # Panel de pestañas para diferentes vistas
        self.collection_view_tabs = QTabWidget()
        
        # Pestaña de datos
        data_tab = QWidget()
        data_tab_layout = QVBoxLayout(data_tab)
        
        data_label = QLabel("Contenido de la Colección:")
        data_tab_layout.addWidget(data_label)
        
        # Create data table if it doesn't exist yet
        if not hasattr(self, 'data_table') or self.data_table is None or sip.isdeleted(self.data_table):
            self.data_table = QTableWidget()
            self.data_table.setAlternatingRowColors(True)
        data_tab_layout.addWidget(self.data_table)
        
        self.collection_view_tabs.addTab(data_tab, "Datos")
        
        # Create tables tab
        tables_tab = QWidget()
        tables_layout = QVBoxLayout(tables_tab)
        
        tables_label = QLabel("Mapeo de Tablas para esta Colección:")
        tables_layout.addWidget(tables_label)
        
        self.tables_tree = QTreeWidget()
        self.tables_tree.setHeaderLabels(["Tabla", "Tipo", "Campos"])
        self.tables_tree.setAlternatingRowColors(True)
        tables_layout.addWidget(self.tables_tree)
        
        self.collection_view_tabs.addTab(tables_tab, "Relaciones de Tablas")
        
        # Pestaña de metadatos
        metadata_tab = QWidget()
        metadata_layout = QVBoxLayout(metadata_tab)
        
        metadata_label = QLabel("Metadatos de la Colección:")
        metadata_layout.addWidget(metadata_label)
        
        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Propiedad", "Valor"])
        self.metadata_table.setAlternatingRowColors(True)
        metadata_layout.addWidget(self.metadata_table)
        
        self.collection_view_tabs.addTab(metadata_tab, "Metadatos")
        
        right_layout.addWidget(self.collection_view_tabs, 4)  # 80% del espacio vertical
        
        # Agregar paneles al splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # Establecer proporción del splitter (30% izquierda, 70% derecha)
        splitter.setSizes([300, 700])
        
        # Agregar splitter al layout principal
        layout.addWidget(splitter)
        
        # Agregar la pestaña al widget de pestañas
        self.tab_widget.addTab(collections_widget, "Colecciones")
        
        # Mark widgets as initialized
        self._widgets_initialized = True

    def show_collections(self):
        """Mostrar las colecciones de la base de datos en el árbol, según el modo de vista activo."""
        if self.db is None:
            return

        try:
            if not self.is_tree_view_valid():
                if not self.ensure_tree_view_exists():
                    print("No se pudo preparar la vista de árbol de colecciones")
                    return

            self.collections_model.clear()
            self._model_items.clear()
            self._db_items.clear()
            if hasattr(self, '_collections_refs'):
                self._collections_refs.clear()

            root_item = self.collections_model.invisibleRootItem()

            # Crear el item de la base de datos para la vista jerárquica
            db_item = QStandardItem(self.database_name)
            db_item.setEditable(False)
            db_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon))

            self._db_items[self.database_name] = db_item
            root_item.appendRow(db_item)

            # Obtener la lista de colecciones de la base de datos
            collections = self.db.list_collection_names()
            total_collections = len(collections)
            print(f"Found {total_collections} collections in database {self.database_name}")

            view_mode = getattr(self, 'view_mode', 0)

            # Vistas agrupadas: eliminar el db_item de la vista jerárquica y delegar
            if view_mode == 1:  # Agrupado por propietario
                root_item.removeRow(0)
                self.create_user_grouped_view(self.collections_model, collections)
                return
            elif view_mode == 2:  # Agrupado por tipo
                root_item.removeRow(0)
                self.create_type_grouped_view(self.collections_model, collections)
                return
            elif view_mode == 3:  # Vista plana
                root_item.removeRow(0)
                self.create_flat_view(self.collections_model, collections)
                return

            # Vista jerárquica (view_mode == 0): mostrar diálogo de progreso para colecciones grandes
            progress = None
            if total_collections > 10:
                progress = QProgressDialog("Cargando colecciones...", "Cancelar", 0, total_collections, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(500)  # Solo mostrar si tarda más de 500ms

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

            # Intentar reiniciar la vista con protección contra recursión
            if not hasattr(self, '_show_collections_recursion_guard'):
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

    def show_collection_owners(self):
        """Mostrar un diálogo con los propietarios de todas las colecciones de la base de datos actual."""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        try:
            owners = self.get_all_collection_owners()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al obtener propietarios: {str(e)}")
            return

        if not owners:
            QMessageBox.information(self, "Información", "No hay colecciones o no se pudo obtener información de propietarios")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Propietarios de Colecciones - {self.database_name}")
        dialog.resize(700, 450)

        layout = QVBoxLayout(dialog)

        info_label = QLabel(f"Se encontraron {len(owners)} colecciones en '{self.database_name}'")
        info_label.setStyleSheet("font-weight: bold; font-size: 13px; margin-bottom: 8px;")
        layout.addWidget(info_label)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Colección", "Propietario", "Email", "Departamento", "Cargo"])
        table.setRowCount(len(owners))
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for row, (collection_name, owner_info) in enumerate(sorted(owners.items())):
            table.setItem(row, 0, QTableWidgetItem(collection_name))
            table.setItem(row, 1, QTableWidgetItem(str(owner_info.get("nombre", "Desconocido"))))
            table.setItem(row, 2, QTableWidgetItem(str(owner_info.get("email", "N/A"))))
            table.setItem(row, 3, QTableWidgetItem(str(owner_info.get("departamento", "N/A"))))
            table.setItem(row, 4, QTableWidgetItem(str(owner_info.get("cargo", "N/A"))))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        dialog.exec()

    # Método auxiliar para reiniciar y mostrar colecciones después de un error
    def reset_and_show_collections(self):
        try:
            # Eliminar protección de recursión
            if hasattr(self, '_show_collections_recursion_guard'):
                delattr(self, '_show_collections_recursion_guard')

            # Reiniciar visualización desde cero
            if hasattr(self, 'collections_model') and self.collections_model:
                self.collections_model.clear()

            self._model_items.clear()
            self._db_items.clear()

            if hasattr(self, '_collections_refs'):
                self._collections_refs.clear()

            # Intentar recrear el tree view si es necesario
            self.ensure_tree_view_exists()
            self.show_collections()

        except Exception as e:
            print(f"Error reiniciando vista de colecciones: {e}")
            QMessageBox.critical(self, "Error", f"Error al reiniciar la vista de colecciones: {str(e)}")

    def setup_query_tab(self):
        """Configurar la pestaña de consultas para ejecutar queries MongoDB"""
        try:
            # Crear widget contenedor
            query_widget = QWidget()
            layout = QVBoxLayout(query_widget)
            
            # Instrucciones
            instructions = QLabel("Ejecutar consultas MongoDB:")
            instructions.setStyleSheet("font-weight: bold;")
            layout.addWidget(instructions)
            
            # Tips and examples
            tips = QLabel("""
Ejemplos de consultas:
- Buscar documentos: db.collection.find({})
- Buscar con filtro: db.collection.find({"campo": "valor"})
- Insertar documento: db.collection.insertOne({"campo": "valor"})
- Actualizar documento: db.collection.updateOne({"campo": "valor"}, {"$set": {"campo": "nuevo"}})
- Eliminar documento: db.collection.deleteOne({"campo": "valor"})
        """)
            layout.addWidget(tips)
        
            # Editor de consultas
            self.query_editor = QTextEdit()
            self.query_editor.setMinimumHeight(100)
            self.query_editor.setPlaceholderText("Introduzca su consulta MongoDB aquí...")
            layout.addWidget(self.query_editor)
            
            # Botones de acción
            button_widget = QWidget()
            button_layout = QHBoxLayout(button_widget)
            
            execute_button = QPushButton("Ejecutar Consulta")
            execute_button.clicked.connect(self.execute_query)
            button_layout.addWidget(execute_button)
            
            clear_button = QPushButton("Limpiar")
            clear_button.clicked.connect(lambda: self.query_editor.clear())
            button_layout.addWidget(clear_button)
            
            button_layout.addStretch()
            layout.addWidget(button_widget)
            
            # Sección de resultados
            results_label = QLabel("Resultados:")
            results_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(results_label)
            
            self.results_view = QTextEdit()
            self.results_view.setReadOnly(True)
            self.results_view.setMinimumHeight(250)
            layout.addWidget(self.results_view)
            
            # Agregar la pestaña al widget de pestañas
            self.tab_widget.addTab(query_widget, "Consultas")
            
            # La pestaña de consultas inicialmente estará deshabilitada hasta que se conecte a una BD
            self.tab_widget.setTabEnabled(2, False)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al configurar la pestaña de consultas: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    def is_tree_view_valid(self):
        """Verifica si la vista de árbol de colecciones existe y es válida"""
        if not self._widget_safe_access:
            return False

        try:
            # Verifica que los widgets principales existan y no estén eliminados
            if not self.collections_tree or sip.isdeleted(self.collections_tree):
                return False
            if not self.collections_model or sip.isdeleted(self.collections_model):
                return False

            # Verifica que el widget no esté destruido y sea visible
            if self._tree_destroyed or not self.collections_tree.isVisible():
                return False

            # Verifica la estructura básica del widget
            if not self.collections_model.rowCount():
                return False
            if not self.collections_tree.parent():
                return False
            if not hasattr(self, '_tree_layout') or not self._tree_layout:
                return False
            if self._tree_layout.indexOf(self.collections_tree) == -1:
                return False
            if not self.collections_tree.window():
                return False

            # Verifica los componentes principales del widget
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

            # Verifica las propiedades básicas del widget
            if not self.collections_tree.font():
                return False
            if not self.collections_tree.palette():
                return False
            if not self.collections_tree.sizePolicy():
                return False
            if not self.collections_tree.style():
                return False
            if not self.collections_tree.layoutDirection():
                return False
            if not self.collections_tree.focusPolicy():
                return False
            if not self.collections_tree.cursor():
                return False
            if not self.collections_tree.windowFlags():
                return False
            if not self.collections_tree.windowState():
                return False
            if not self.collections_tree.windowOpacity():
                return False
            if not self.collections_tree.windowTitle():
                return False
            if not self.collections_tree.windowIcon():
                return False
            if not self.collections_tree.windowModality():
                return False
            if not self.collections_tree.windowType():
                return False
            if not self.collections_tree.windowFilePath():
                return False
            if not self.collections_tree.windowRole():
                return False
            if not self.collections_tree.windowTransparency():
                return False

            return True

        except Exception as e:
            print(f"Error validando la vista de árbol: {e}")
            return False

    def enable_database_actions(self, enabled):
        """Habilita/deshabilita las acciones de menú que requieren conexión activa."""
        action_names = (
            "disconnect_action", "list_db_action", "list_db_owner_action",
            "list_table_owners_action", "switch_db_action", "stats_action",
            "edit_fields_action", "view_collections_action", "create_collection_action",
            "drop_collection_action", "list_users_action", "search_user_action",
            "edit_user_action", "password_action", "import_action", "index_action",
        )
        for name in action_names:
            action = getattr(self, name, None)
            if action is not None:
                action.setEnabled(enabled)

    def update_connection_status(self, connected):
        """Update UI elements based on connection status"""
        try:
            if connected:
                # Update connection status label
                self.connection_status_label.setText(f"Conectado a: {self.database_name}")
                self.connection_status_label.setStyleSheet("color: green; padding: 3px;")

                # Enable database-related actions
                self.enable_database_actions(True)

                # Enable tabs
                if hasattr(self, 'tab_widget'):
                    self.tab_widget.setTabEnabled(1, True)  # Colecciones tab
                    self.tab_widget.setTabEnabled(2, True)  # Consultas tab
            else:
                # Update connection status label
                self.connection_status_label.setText("No conectado")
                self.connection_status_label.setStyleSheet("color: red; padding: 3px;")

                # Disable database-related actions
                self.enable_database_actions(False)

                # Disable tabs
                if hasattr(self, 'tab_widget'):
                    self.tab_widget.setTabEnabled(1, False)  # Colecciones tab
                    self.tab_widget.setTabEnabled(2, False)  # Consultas tab
        except Exception as e:
            print(f"Error updating connection status: {e}")
            traceback.print_exc()

    def _connect_to_database(self, connection_string, database_name):
        """Conecta a MongoDB y deja el estado de la ventana listo para usar.

        Crea el MongoClient, hace ping, asigna self.client/self.db/self.database_name/
        self.connection_string, refresca la UI (colecciones, estadísticas, pestañas) y
        emite connection_status_changed(True).

        No captura excepciones: el llamador decide cómo informar del fallo.
        """
        client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        # Verificar conexión
        client.admin.command('ping')

        # Guardar referencias
        self.client = client
        self.db = client[database_name]
        self.connection_string = connection_string
        self.database_name = database_name

        # Actualizar interfaz
        self.show_status_message(f"Conectado a {database_name}")

        # Habilitar pestañas y acciones
        self.tab_widget.setTabEnabled(1, True)  # Pestaña de colecciones
        self.tab_widget.setTabEnabled(2, True)  # Pestaña de consultas

        # Mostrar colecciones
        self.show_collections()

        # Actualizar estadísticas
        self.update_database_stats()

        # Enviar señal de conexión establecida
        self.connection_status_changed.emit(True)

    def initialize_connection(self):
        """Intento de conexión automática al arrancar, usando MONGODB_URI del entorno.

        Llamado desde main_gui.py vía QTimer.singleShot tras mostrar la ventana. A
        diferencia de open_connection_dialog, no bloquea el arranque con un QMessageBox
        si falla: es un intento silencioso, y el usuario siempre puede conectar
        manualmente después.
        """
        if not self.connection_string:
            return
        if self.connection_in_progress:
            return

        database_name = os.environ.get("MONGODB_DATABASE") or self.database_name

        self.connection_in_progress = True
        self.show_status_message(f"Conectando automáticamente a {database_name}...", timeout=0)

        try:
            self._connect_to_database(self.connection_string, database_name)

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"Error de conexión automática: {e}")
            self.show_status_message(
                f"No se pudo conectar automáticamente a MongoDB: {e}. "
                "Use Conexión > Conectar para conectarse manualmente.",
                error=True,
            )

        except Exception as e:
            print(f"Error inesperado durante la conexión automática: {e}")
            traceback.print_exc()
            self.show_status_message(
                f"Error al conectar automáticamente: {e}. "
                "Use Conexión > Conectar para conectarse manualmente.",
                error=True,
            )

        finally:
            self.connection_in_progress = False

    def open_connection_dialog(self):
        """Abrir el diálogo de conexión a MongoDB"""
        try:
            # Crear diálogo de conexión
            dialog = ConnectionDialog(self, self.connection_string)

            # Si el diálogo es aceptado
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Obtener datos de conexión
                connection_data = dialog.get_connection_data()
                connection_string = connection_data["connection_string"]
                database_name = connection_data["database"]

                # Intentar conectar a MongoDB
                self.show_status_message(f"Conectando a {database_name}...", timeout=0)

                try:
                    self._connect_to_database(connection_string, database_name)

                except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                    QMessageBox.critical(self, "Error de Conexión",
                                        f"No se pudo conectar a MongoDB: {str(e)}\n\n"
                                        "Verifique la cadena de conexión y que el servidor esté en ejecución.")
                    self.show_status_message("Error de conexión", error=True)

                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error al conectar a MongoDB: {str(e)}")
                    self.show_status_message(f"Error: {str(e)}", error=True)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir diálogo de conexión: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)

    def disconnect_database(self):
        """Cierra la conexión activa a MongoDB y deja la ventana en estado 'no conectado'."""
        try:
            if self.client is not None:
                self.client.close()
        except Exception as e:
            print(f"Error closing MongoDB connection: {e}")
        finally:
            self.client = None
            self.db = None
            self.current_collection = None

        if hasattr(self, 'collections_model') and self.collections_model is not None:
            self.collections_model.clear()

        self.show_status_message("Desconectado de MongoDB")
        self.connection_status_changed.emit(False)

    def setup_menu_bar(self):
        """Configura la barra de menús con los menús y acciones necesarios"""
        menu_bar = self.menuBar()
        
        # Connection menu
        connection_menu = menu_bar.addMenu("&Conexión")
        
        # Connect action
        connect_action = QAction("&Conectar...", self)
        connect_action.setStatusTip("Conectar a la base de datos MongoDB")
        connect_action.triggered.connect(self.open_connection_dialog)
        connection_menu.addAction(connect_action)
        
        # Disconnect action
        disconnect_action = QAction("&Desconectar", self)
        disconnect_action.setStatusTip("Desconectar de la base de datos MongoDB")
        disconnect_action.triggered.connect(self.disconnect_database)
        disconnect_action.setEnabled(False)
        connection_menu.addAction(disconnect_action)
        self.disconnect_action = disconnect_action
        
        connection_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("&Salir", self)
        exit_action.setStatusTip("Salir de la aplicación")
        exit_action.triggered.connect(self.close)
        connection_menu.addAction(exit_action)
        
        # Database menu
        database_menu = menu_bar.addMenu("&Base de Datos")
        
        # List databases action
        list_db_action = QAction("&Listar Bases de Datos", self)
        list_db_action.setStatusTip("Mostrar todas las bases de datos disponibles")
        list_db_action.triggered.connect(self.show_databases)
        list_db_action.setEnabled(False)
        database_menu.addAction(list_db_action)
        self.list_db_action = list_db_action
        
        # List databases by owner action
        list_db_owner_action = QAction("&Listar por Propietario", self)
        list_db_owner_action.setStatusTip("Mostrar bases de datos agrupadas por propietario")
        list_db_owner_action.triggered.connect(self.list_databases_by_owner)
        list_db_owner_action.setEnabled(False)
        database_menu.addAction(list_db_owner_action)
        self.list_db_owner_action = list_db_owner_action

        # List table owners action
        list_table_owners_action = QAction("&Listar Propietarios de Tablas", self)
        list_table_owners_action.setStatusTip("Mostrar propietarios de tablas/colecciones específicas")
        list_table_owners_action.triggered.connect(self.list_table_owners)
        list_table_owners_action.setEnabled(False)
        database_menu.addAction(list_table_owners_action)
        self.list_table_owners_action = list_table_owners_action

        # Switch database action
        switch_db_action = QAction("&Cambiar Base de Datos", self)
        switch_db_action.setStatusTip("Cambiar a otra base de datos")
        switch_db_action.triggered.connect(self.switch_database)
        switch_db_action.setEnabled(False)
        database_menu.addAction(switch_db_action)
        self.switch_db_action = switch_db_action
        
        database_menu.addSeparator()
        
        # Global stats action
        stats_action = QAction("&Estadísticas Globales", self)
        stats_action.setStatusTip("Ver estadísticas globales de MongoDB")
        stats_action.triggered.connect(self.show_global_stats)
        stats_action.setEnabled(False)
        database_menu.addAction(stats_action)
        self.stats_action = stats_action
        
        # Edit database fields action
        edit_fields_action = QAction("&Editar Campos de Base de Datos", self)
        edit_fields_action.setStatusTip("Editar estructura y campos de la base de datos")
        edit_fields_action.triggered.connect(self.edit_database_fields)
        edit_fields_action.setEnabled(False)
        database_menu.addAction(edit_fields_action)
        self.edit_fields_action = edit_fields_action
        
        # Collections menu
        collections_menu = menu_bar.addMenu("&Colecciones")
        
        # View collections action
        view_collections_action = QAction("&Ver Colecciones", self)
        view_collections_action.setStatusTip("Ver todas las colecciones en la base de datos")
        view_collections_action.triggered.connect(self.show_collections)
        view_collections_action.setEnabled(False)
        collections_menu.addAction(view_collections_action)
        self.view_collections_action = view_collections_action
        
        # Create collection action
        create_collection_action = QAction("&Crear Colección", self)
        create_collection_action.setStatusTip("Crear una nueva colección")
        create_collection_action.triggered.connect(self.create_collection)
        collections_menu.addAction(create_collection_action)
        
        # View menu
        view_menu = menu_bar.addMenu("&Vista")
        
        # Refresh action
        self.action_refresh = QAction("&Actualizar Vista", self)
        self.action_refresh.setShortcut("F5")
        self.action_refresh.setStatusTip("Actualizar la vista actual")
        view_menu.addAction(self.action_refresh)
        
        # Store reference to create collection action
        self.create_collection_action = create_collection_action
        
        # Drop collection action
        drop_collection_action = QAction("&Eliminar Colección", self)
        drop_collection_action.setStatusTip("Eliminar una colección")
        drop_collection_action.triggered.connect(self.drop_collection)
        drop_collection_action.setEnabled(False)
        collections_menu.addAction(drop_collection_action)
        self.drop_collection_action = drop_collection_action
        
        # User Management menu
        user_menu = menu_bar.addMenu("&Usuarios")
        
        # List users action
        list_users_action = QAction("&Listar Usuarios", self)
        list_users_action.setStatusTip("Listar todos los usuarios en las colecciones")
        list_users_action.triggered.connect(self.list_users)
        list_users_action.setEnabled(False)
        user_menu.addAction(list_users_action)
        self.list_users_action = list_users_action
        
        # Search user action
        search_user_action = QAction("&Buscar Usuario", self)
        search_user_action.setStatusTip("Buscar un usuario específico")
        search_user_action.triggered.connect(self.search_user)
        search_user_action.setEnabled(False)
        user_menu.addAction(search_user_action)
        self.search_user_action = search_user_action
        
        # Edit user action
        edit_user_action = QAction("&Editar Usuario", self)
        edit_user_action.setStatusTip("Editar información de usuario")
        edit_user_action.triggered.connect(self.edit_user)
        edit_user_action.setEnabled(False)
        user_menu.addAction(edit_user_action)
        self.edit_user_action = edit_user_action
        
        user_menu.addSeparator()
        
        # Password management action
        password_action = QAction("&Gestión de Contraseñas", self)
        password_action.setStatusTip("Gestionar contraseñas de usuarios")
        password_action.triggered.connect(self.manage_password)
        password_action.setEnabled(False)
        user_menu.addAction(password_action)
        self.password_action = password_action
        
        # Tools menu
        tools_menu = menu_bar.addMenu("&Herramientas")
        
        # Import Data
        import_action = QAction("Importar Datos", self)
        import_action.setStatusTip("Importar datos desde archivos JSON o CSV")
        import_action.triggered.connect(self.import_data)
        tools_menu.addAction(import_action)
        self.import_action = import_action
        
        # Manage indexes
        indexes_action = QAction("Gestionar Índices", self)
        indexes_action.setStatusTip("Crear y gestionar índices de la base de datos")
        indexes_action.triggered.connect(self.manage_indexes)
        tools_menu.addAction(indexes_action)
        self.index_action = indexes_action
        
        # Backup and Restore submenu
        backup_menu = tools_menu.addMenu("Respaldo y Restauración")
        
        # Backup Database
        backup_action = QAction("Realizar Respaldo", self)
        backup_action.setStatusTip("Realizar respaldo de la base de datos")
        backup_action.triggered.connect(self.backup_database)
        backup_menu.addAction(backup_action)
        
        # Restore Database
        restore_action = QAction("Restaurar desde Respaldo", self)
        restore_action.setStatusTip("Restaurar la base de datos desde respaldo")
        backup_menu.addAction(restore_action)
        restore_action.triggered.connect(self.restore_database)
    def limpiar_recursos(self):
        """Clean up resources and disconnect signals to prevent memory leaks"""
        try:
            print("\n--- Cleaning up resources ---")
            
            # Clear model item references first
            try:
                if hasattr(self, '_model_items'):
                    self._model_items.clear()
                    print("Model item references cleared")
                if hasattr(self, '_db_items'):
                    self._db_items.clear()
                    print("Database item references cleared")
            except Exception as e:
                print(f"Error clearing model item references: {e}")
                
            # Disconnect signals where possible - do this before clearing the model
            try:
                if hasattr(self, 'connection_status_changed'):
                    self.connection_status_changed.disconnect()
                
                # Disconnect tree signals if it exists
                if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
                    try:
                        self.collections_tree.doubleClicked.disconnect()
                    except:
                        pass
                print("Signals disconnected")
            except Exception as e:
                print(f"Error disconnecting signals: {e}")
            
            # Set tree model to None before clearing the model
            if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
                try:
                    self.collections_tree.setModel(None)
                except Exception as e:
                    print(f"Error setting model to None: {e}")
            
        except Exception as e:
            print(f"Error in limpiar_recursos: {e}")
            traceback.print_exc()
            
    def update_database_stats(self):
        """Update the database statistics display"""
        try:
            # Get database stats
            stats = self.db.command("dbStats")
            
            # Format stats as HTML
            # Format statistics as HTML
            data_size_mb = stats.get('dataSize', 0) / (1024*1024)
            storage_size_mb = stats.get('storageSize', 0) / (1024*1024)
            index_size_mb = stats.get('indexSize', 0) / (1024*1024)
            
            formatted_stats = f"""
            <h3>Database: {self.database_name}</h3>
            <p><b>Collections:</b> {stats.get('collections', 0)}</p>
            <p><b>Views:</b> {stats.get('views', 0)}</p>
            <p><b>Objects:</b> {stats.get('objects', 0)}</p>
            <p><b>Data Size:</b> {data_size_mb:.2f} MB</p>
            <p><b>Storage Size:</b> {storage_size_mb:.2f} MB</p>
            <p><b>Indexes:</b> {stats.get('indexes', 0)}</p>
            <p><b>Index Size:</b> {index_size_mb:.2f} MB</p>
            """
            self.stats_content.setHtml(formatted_stats)
            return True
        except Exception as e:
            self.show_status_message(f"Error updating statistics: {e}", error=True)
            print(f"Error in update_database_stats: {e}")
            return False
    def ensure_tree_view_exists(self):
        """Ensure the collections tree view exists and is valid, recreate if needed"""
        # Reset attempts counter if tree is being recreated after a long time
        import time
        current_time = time.time()
        if not hasattr(self, '_last_tree_recreation_time') or current_time - self._last_tree_recreation_time > 60:
            self._tree_recreation_attempts = 0
        self._last_tree_recreation_time = current_time
        
        # Increment attempts counter
        self._tree_recreation_attempts += 1
        
        # Define max recreation attempts constant
        MAX_RECREATION_ATTEMPTS = 3
        
        # Check if we've reached maximum attempts
        if self._tree_recreation_attempts >= MAX_RECREATION_ATTEMPTS:
            print(f"Maximum tree view recreation attempts ({MAX_RECREATION_ATTEMPTS}) reached")
            return False
        
        print(f"Attempting to recreate tree view (attempt {self._tree_recreation_attempts})")
        
        # Check if the tree widget container exists and is valid
        if not hasattr(self, 'tree_widget') or self.tree_widget is None or sip.isdeleted(self.tree_widget):
            print("Tree widget container is missing or invalid, cannot recreate tree view")
            return False
        
        # Initialize tree layout
        tree_layout = None
        
        # First check if we have a stored layout
        if hasattr(self, '_tree_layout') and self._tree_layout and not sip.isdeleted(self._tree_layout):
            print("Using stored tree layout reference")
            tree_layout = self._tree_layout
        else:
            # Try to find layout in tree widget children
            try:
                print("Searching for layout in tree widget children")
                layout_found = False
                for child in self.tree_widget.children():
                    if isinstance(child, QVBoxLayout) or isinstance(child, QHBoxLayout) or isinstance(child, QLayout):
                        tree_layout = child
                        self._tree_layout = child  # Store for future use
                        layout_found = True
                        print("Found layout in tree widget children")
                        break
                
                if not layout_found:
                    print("Could not find layout in tree widget children")
                    # If no layout is found, try to get the layout directly from the widget
                    tree_layout = self.tree_widget.layout()
                    if tree_layout:
                        self._tree_layout = tree_layout
                        print("Using widget's direct layout")
                    else:
                        print("Tree widget has no layout, cannot recreate tree view")
                        return False
            except Exception as layout_error:
                print(f"Error finding layout: {layout_error}")
                traceback.print_exc()
                print("Tree widget container is missing or invalid, cannot recreate tree view")
                return False
        
        # Before creating a new tree view, make sure we properly clean up any existing one
        if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
            try:
                print("Removing existing tree view from layout")
                # First disconnect signals to prevent callbacks during deletion
                try:
                    self.collections_tree.doubleClicked.disconnect()
                except Exception:
                    pass
                
                # Remove from layout before deleting
                if tree_layout:
                    tree_layout.removeWidget(self.collections_tree)
                
                # Set model to None to break reference cycles
                self.collections_tree.setModel(None)
                
                # Schedule deletion
                self.collections_tree.deleteLater()
            except Exception as cleanup_error:
                print(f"Error during tree view cleanup: {cleanup_error}")
                traceback.print_exc()
        
        # Clear all references to prevent memory leaks
        self._model_items.clear()
        self._db_items.clear()
        if hasattr(self, '_collections_refs'):
            self._collections_refs.clear()
        else:
            self._collections_refs = {}
        
        # Create or clear model
        if not hasattr(self, 'collections_model') or self.collections_model is None:
            print("Creating new QStandardItemModel")
            self.collections_model = QStandardItemModel()
        else:
            print("Clearing existing QStandardItemModel")
            self.collections_model.clear()
        
        # Process events to ensure Qt has handled previous operations
        QApplication.processEvents()
        
        # Try to create a new tree view
        try:
            print("Creating new QTreeView")
            # Create a new tree view
            self.collections_tree = QTreeView(self.tree_widget)
            self.collections_tree.setHeaderHidden(True)
            self.collections_tree.setMinimumWidth(250)
            self.collections_tree.setObjectName("collectionsTreeView")
            
            # Set the model after tree view is created
            self.collections_tree.setModel(self.collections_model)
            
            # Add to layout
            if tree_layout:
                print("Adding new tree view to layout")
                tree_layout.addWidget(self.collections_tree)
                
            # Connect signals
            print("Connecting double-click signal")
            self.collections_tree.doubleClicked.connect(self.view_collection_data)
            
            # Mark tree as not destroyed
            self._tree_destroyed = False
            
            print("Tree view recreation successful")
            return True
        except Exception as e:
            print(f"Error recreating collections tree: {e}")
            traceback.print_exc()
            return False
        if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
            try:
                print("Removing existing tree view from layout")
                # Disconnect any existing signals
                try:
                    self.collections_tree.doubleClicked.disconnect()
                except Exception:
                    pass
                
                # Remove from layout before deleting
                if tree_layout:
                    tree_layout.removeWidget(self.collections_tree)
                
                # Set model to None to break reference cycles
                self.collections_tree.setModel(None)
                
                # Schedule deletion
                self.collections_tree.deleteLater()
            except Exception as cleanup_error:
                print(f"Error during tree view cleanup: {cleanup_error}")
                traceback.print_exc()
        
        # Clear references to prevent memory leaks
        self._model_items.clear()
        self._db_items.clear()
        if hasattr(self, '_collections_refs'):
            self._collections_refs.clear()
        else:
            self._collections_refs = {}
        
        # Create a new model if needed
        if not hasattr(self, 'collections_model') or self.collections_model is None:
            print("Creating new QStandardItemModel")
            self.collections_model = QStandardItemModel()
        else:
            print("Clearing existing QStandardItemModel")
            self.collections_model.clear()
        
        # Wait a moment to ensure Qt has processed pending events
        QApplication.processEvents()
        
        # Try to create a new tree view
        try:
            print("Creating new QTreeView")
            # Create a new tree view
            self.collections_tree = QTreeView(self.tree_widget)
            self.collections_tree.setHeaderHidden(True)
            self.collections_tree.setMinimumWidth(250)
            self.collections_tree.setObjectName("collectionsTreeView")
            
            # Set the model after tree view is created
            self.collections_tree.setModel(self.collections_model)
            
            # Add to layout
            if tree_layout:
                print("Adding new tree view to layout")
                tree_layout.addWidget(self.collections_tree)
                
            # Connect signals
            print("Connecting double-click signal")
            self.collections_tree.doubleClicked.connect(self.view_collection_data)
            
            # Mark tree as not destroyed
            self._tree_destroyed = False
            
            print("Tree view recreation successful")
            return True
        except Exception as e:
            print(f"Error recreating collections tree: {e}")
            traceback.print_exc()
            return False
            try:
                print("Removing existing tree view from layout")
                # Disconnect any existing signals
                try:
                    self.collections_tree.doubleClicked.disconnect()
                except Exception:
                    pass
                
                # Remove from layout before deleting
                if tree_layout:
                    tree_layout.removeWidget(self.collections_tree)
                
                # Set model to None to break reference cycles
                self.collections_tree.setModel(None)
                
                # Schedule deletion
                self.collections_tree.deleteLater()
            except Exception as cleanup_error:
                print(f"Error during tree view cleanup: {cleanup_error}")
        
        # Clear references to prevent memory leaks
        self._model_items.clear()
        self._db_items.clear()
        self._collections_refs.clear()
        
        # Create a new model if needed
        if not hasattr(self, 'collections_model') or self.collections_model is None:
            print("Creating new QStandardItemModel")
            self.collections_model = QStandardItemModel()
        else:
            print("Clearing existing QStandardItemModel")
            self.collections_model.clear()
        
        # Wait a moment to ensure Qt has processed pending events
        QApplication.processEvents()
        
        # Try to create a new tree view
        try:
            print("Creating new QTreeView")
            # Create a new tree view
            self.collections_tree = QTreeView(self.tree_widget)
            self.collections_tree.setHeaderHidden(True)
            self.collections_tree.setMinimumWidth(250)
            self.collections_tree.setObjectName("collectionsTreeView")
            
            # Set the model after tree view is created
            self.collections_tree.setModel(self.collections_model)
            
            # Add to layout
            if tree_layout:
                print("Adding new tree view to layout")
                tree_layout.addWidget(self.collections_tree)
                
            # Connect signals
            print("Connecting double-click signal")
            self.collections_tree.doubleClicked.connect(self.view_collection_data)
            
            # Mark tree as not destroyed
            self._tree_destroyed = False
            
            print("Tree view recreation successful")
            return True
        except Exception as e:
            print(f"Error recreating collections tree: {e}")
            traceback.print_exc()
            return False
        MAX_RECREATION_ATTEMPTS = 3
        
        # Check if we've reached maximum attempts
        if self._tree_recreation_attempts >= MAX_RECREATION_ATTEMPTS:
            print(f"Maximum tree view recreation attempts ({MAX_RECREATION_ATTEMPTS}) reached")
            return False
        
        # Initialize tree layout
        tree_layout = None
        
        # First check if we have a stored layout
        if hasattr(self, '_tree_layout') and self._tree_layout:
            tree_layout = self._tree_layout
        else:
            # Try to find layout in tree widget children
            try:
                for child in self.tree_widget.children():
                    if isinstance(child, QLayout):
                        tree_layout = child
                        self._tree_layout = child  # Store for future use
                        break
                
                if not tree_layout:
                    print("Could not find layout in tree widget children")
                    print("Tree widget container is missing, cannot recreate tree view")
                    return False
            except Exception as layout_error:
                print(f"Error finding layout: {layout_error}")
                print("Tree widget container is missing, cannot recreate tree view")
                return False
                
        # Try to create a new tree view
        try:
            # Clear existing model items and references
            self._model_items.clear()
            self._db_items.clear()
            
            # Create a new model if needed
            if not hasattr(self, 'collections_model') or self.collections_model is None:
                self.collections_model = QStandardItemModel()
            # Create a new tree view
            self.collections_tree = QTreeView(self.tree_widget)
            self.collections_tree.setHeaderHidden(True)
            self.collections_tree.setMinimumWidth(250)
            self.collections_tree.setObjectName("collectionsTreeView")
            self.collections_tree.setModel(self.collections_model)
            
            # Add to layout
            if tree_layout:
                tree_layout.addWidget(self.collections_tree)
                
            # Connect signals
            self.collections_tree.doubleClicked.connect(self.view_collection_data)
            
            return True
        except Exception as e:
            print(f"Error recreating collections tree: {e}")
            return False
    def refresh_ui(self):
        """Refresh the user interface"""
        try:
            print("Starting UI refresh...")
            
            # UI adjustments based on connection status
            if hasattr(self, 'db') and self.db:
                # Enable collections tab
                if hasattr(self, 'tab_widget') and hasattr(self, 'collections_tab'):
                    pass  # Add proper action here if needed
            
            # Process pending events before updating UI
            QApplication.processEvents()
            
            # Refresh data table if it exists and is valid
            if hasattr(self, 'data_table') and self.data_table:
                try:
                    if not sip.isdeleted(self.data_table) and self.data_table.isVisible():
                        print("Refreshing data table")
                        self.data_table.viewport().update()
                except RuntimeError:
                    print("Data table exists but can't be accessed (RuntimeError)")
                except Exception as e:
                    print(f"Error refreshing data table: {e}")
            
            # Refresh collections tree if it exists and is valid, or try to recreate it
            tree_valid = self.is_tree_view_valid()
            if tree_valid:
                try:
                    print("Refreshing collections tree viewport")
                    self.collections_tree.viewport().update()
                    
                    # If tree is empty but should have items, reload collections
                    if self.db and self.collections_model and self.collections_model.rowCount() == 0:
                        print("Collections tree is empty, reloading collections")
                        self.show_collections()
                except Exception as e:
                    print(f"Error updating collections tree viewport: {e}")
                    tree_valid = False
            
            # If tree is not valid but container exists, try to recreate it
            if not tree_valid and hasattr(self, 'tree_widget') and self.tree_widget and not sip.isdeleted(self.tree_widget):
                print("Collections tree is invalid, attempting recreation")
                if self.ensure_tree_view_exists():
                    print("Collections tree recreated during UI refresh")
                    try:
                        # After recreation, show collections
                        if self.db:
                            self.show_collections()
                    except Exception as reload_error:
                        print(f"Error reloading collections after tree recreation: {reload_error}")
            
            # Update status and connection labels
            if hasattr(self, 'status_label') and self.status_label and not sip.isdeleted(self.status_label):
                self.status_label.update()
            
            if hasattr(self, 'connection_status_label') and self.connection_status_label and not sip.isdeleted(self.connection_status_label):
                if hasattr(self, 'tab_widget') and hasattr(self, 'collections_tab'):
                    pass  # Add proper action here if needed
                
            if hasattr(self, 'data_table') and self.data_table and not sip.isdeleted(self.data_table):
                if self.data_table.isVisible():
                    self.data_table.viewport().update()
            
            # Refresh collections tree if it exists and is valid, or try to recreate it
            if self.is_tree_view_valid():
                self.collections_tree.viewport().update()
            elif hasattr(self, 'tree_widget') and self.tree_widget and not sip.isdeleted(self.tree_widget):
                # Try to recreate the tree view if the parent widget still exists
                if self.ensure_tree_view_exists():
                    print("Collections tree recreated during UI refresh")
                    self.collections_tree.viewport().update()
            
            print("UI refresh completed")
            return True
            
        except Exception as e:
            print(f"Error refreshing UI: {e}")
            traceback.print_exc()
            return False

    def view_collection_data(self, index):
        """Handle double-click event on collections tree to view collection data"""
        try:
            if not index.isValid() or not self.db:
                return
                
            # Get the model from the index
            model = index.model()
            if not model:
                return
                
            # Get item from the model
            item = model.itemFromIndex(index)
            if not item:
                return
                
            # Get the collection name from the item text
            # Format is typically "collection_name (N docs)"
            item_text = item.text()
            collection_name = item_text.split(" (")[0] if " (" in item_text else item_text
            
            # Check if collection exists
            if collection_name not in self.db.list_collection_names():
                print(f"Collection {collection_name} not found")
                return
                
            # Set current collection
            self.current_collection = collection_name
            
            # Load collection data with a reasonable limit
            self.show_collection_data(collection_name, limit=100, with_metadata=True)
            
            # Set the tabs to show the data tab
            if hasattr(self, 'collection_view_tabs'):
                self.collection_view_tabs.setCurrentIndex(0)
                
            # Update status message
            self.show_status_message(f"Mostrando datos de {collection_name}")
            
        except Exception as e:
            print(f"Error viewing collection data: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error al mostrar datos de colección: {str(e)}")
            
    def show_collection_data(self, collection_name, limit=100, with_metadata=False):
        """Show data from the specified collection in the data table"""
        try:
                if self.db is None:
                    return

                collection = self.db[collection_name]
                documents = collection.find().limit(limit)

                # Verificar que self.data_table no es None antes de usarlo
                if hasattr(self, 'data_table') and self.data_table is not None:
                    # Clear the table
                    self.data_table.clear()
                    self.data_table.setRowCount(0)
                    self.data_table.setColumnCount(0)
                    
                    # Asegurarse de que la tabla de datos tenga un padre
                    if self.data_table.parent() is None:
                        if hasattr(self, 'collections_tab_widget'):
                            # Buscar el layout adecuado para la tabla de datos
                            data_tab = self.collections_tab_widget.widget(0)
                            if data_tab and data_tab.layout():
                                data_tab.layout().addWidget(self.data_table)
                # Convert documents to list to check if empty
                documents_list = list(documents)
                
                if not documents_list:
                    self.show_status_message(f"Collection '{collection_name}' is empty")
                    return
                    
                # Get all possible field names from the documents
                all_fields = set()
                for doc in documents_list:
                    all_fields.update(doc.keys())
                    
                # Remove internal MongoDB fields from display if desired
                if '_id' in all_fields:
                    all_fields.remove('_id')
                    
                # Convert to list and sort for consistent display
                field_list = ['_id'] + sorted(list(all_fields))
                
                # Set up the table
                try:
                    self.data_table.setColumnCount(len(field_list))
                    self.data_table.setHorizontalHeaderLabels(field_list)
                    
                    # Add data to the table
                    for row_idx, doc in enumerate(documents_list):
                        self.data_table.insertRow(row_idx)
                        for col_idx, field in enumerate(field_list):
                            if field in doc:
                                # Convert value to string for display
                                value = str(doc[field])
                                item = QTableWidgetItem(value)
                                self.data_table.setItem(row_idx, col_idx, item)
                    
                    # Resize columns to content
                    self.data_table.resizeColumnsToContents()
                    
                    total_docs = collection.count_documents({})
                    self.show_status_message(f"Showing {min(limit, total_docs)} of {total_docs} documents in '{collection_name}'")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to load collection data: {str(e)}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al configurar la vista de colección: {str(e)}")
            
    def load_collection_metadata(self, collection_name):
        try:
            if not hasattr(self, 'meta_collection_name'):
                # Si la UI no se ha configurado, salir
                return
                
            collection = self.db[collection_name]
            
            # Información general
            self.meta_collection_name.setText(collection_name)
            
            # Contar documentos
            doc_count = collection.count_documents({})
            self.meta_document_count.setText(str(doc_count))
            
            # Obtener estadísticas de la colección
            try:
                stats = self.db.command("collStats", collection_name)
                size_mb = stats.get("size", 0) / (1024 * 1024)
                self.meta_size.setText(f"{size_mb:.2f} MB")
                
                avg_size_kb = stats.get("avgObjSize", 0) / 1024
                self.meta_avg_doc_size.setText(f"{avg_size_kb:.2f} KB")
                
                # Índices
                index_count = len(list(collection.list_indexes()))
                self.meta_indexes.setText(str(index_count))
                
                index_size_mb = stats.get("totalIndexSize", 0) / (1024 * 1024)
                self.meta_index_size.setText(f"{index_size_mb:.2f} MB")
            except Exception as stats_error:
                print(f"Error al obtener estadísticas: {stats_error}")
            
            # Detectar tipo de contenido
            content_type = self.detect_collection_content_type(collection_name)
            self.meta_content_type.setText(content_type)
            
            # Buscar propietario de la colección
            owner_info = self.find_collection_owner(collection_name)
            
            # Actualizar información del propietario
            self.meta_owner_name.setText(owner_info.get("nombre", "Desconocido"))
            self.meta_owner_email.setText(owner_info.get("email", "N/A"))
            self.meta_owner_department.setText(owner_info.get("departamento", "N/A"))
            self.meta_owner_role.setText(owner_info.get("cargo", "N/A"))
            
            # Fechas de creación y modificación
            try:
                # Intentar obtener fecha de creación a partir del ObjectId del primer documento
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
                
                # Intentar obtener fecha de última modificación del documento más reciente
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
            
            # Estructura de campos
            self.meta_fields_table.setRowCount(0)
            if doc_count > 0:
                sample_doc = collection.find_one()
                if sample_doc:
                    field_infos = []
                    for field, value in sample_doc.items():
                        field_type = type(value).__name__
                        description = self.get_field_description(field)
                        field_infos.append((field, field_type, description))
                    
                    # Ordenar por nombre de campo
                    field_infos.sort(key=lambda x: x[0])
                    
                    # Añadir a la tabla
                    self.meta_fields_table.setRowCount(len(field_infos))
                    for i, (field, field_type, description) in enumerate(field_infos):
                        self.meta_fields_table.setItem(i, 0, QTableWidgetItem(field))
                        self.meta_fields_table.setItem(i, 1, QTableWidgetItem(field_type))
                        self.meta_fields_table.setItem(i, 2, QTableWidgetItem(description))
                    
                    self.meta_fields_table.resizeColumnsToContents()
            
            # Historial de acceso
            self.load_access_history(collection_name)
            
        except Exception as e:
            print(f"Error al cargar metadatos: {e}")
        
    def detect_collection_content_type(self, collection_name):
        """Detecta el tipo de contenido de una colección basado en su estructura"""
        try:
            collection = self.db[collection_name]
            # Obtener cantidad de documentos
            doc_count = collection.count_documents({})
            
            if doc_count == 0:
                return "Colección vacía"
                
            # Obtener una muestra de documentos para análisis
            sample_docs = list(collection.find().limit(10))
            if not sample_docs:
                return "Desconocido"

            # Analizar la estructura de los documentos
            field_types = {}
            data_rows_count = 0
            has_table_structure = True
            has_geospatial_data = False
            has_complex_objects = False
            
            # Campos comunes en datos de Excel exportados
            excel_fields = ["sheet_name", "row", "col", "header", "value", "format"]
            excel_match_count = 0
            
            # Verificar si tiene índices de texto (para documentos de texto)
            text_index = False
            for idx in collection.list_indexes():
                for field, type_val in idx.get('key', {}).items():
                    if type_val == 'text':
                        text_index = True
                        break
            
            # Verificar campos para datos geoespaciales
            for doc in sample_docs:
                # Verificar estructura de tabla (documentos similares)
                if data_rows_count == 0:
                    first_doc_fields = set(doc.keys())
                else:
                    if set(doc.keys()) != first_doc_fields:
                        has_table_structure = False
                
                # Verificar si parece una exportación de Excel
                excel_fields_found = sum(1 for field in excel_fields if field in doc)
                if excel_fields_found >= 3:
                    excel_match_count += 1
                
                # Verificar campos para datos geoespaciales
                for field, value in doc.items():
                    # Registrar tipo de campo
                    field_type = type(value).__name__
                    if field not in field_types:
                        field_types[field] = set()
                    field_types[field].add(field_type)
                    
                    # Verificar si es un objeto geoespacial
                    if field in ['location', 'coordinates', 'geometry'] and isinstance(value, dict):
                        if 'type' in value and 'coordinates' in value:
                            has_geospatial_data = True
                    
                    # Verificar si tiene objetos complejos anidados
                    if isinstance(value, dict) and len(value) > 3:
                        has_complex_objects = True
                
                data_rows_count += 1
            
            # Determinar tipo basado en análisis
            if excel_match_count >= min(3, len(sample_docs)):
                return "Datos de Excel"
            elif text_index:
                return "Documentos de texto"
            elif has_geospatial_data:
                return "Datos geoespaciales"
            elif has_table_structure and not has_complex_objects:
                return "Tabla de datos"
            elif collection_name.lower() in ['users', 'usuarios', 'clientes', 'customers']:
                return "Datos de usuarios"
            elif collection_name.lower() in ['products', 'productos', 'inventory', 'inventario']:
                return "Catálogo de productos"
            elif collection_name.lower() in ['logs', 'audit', 'eventos', 'events']:
                return "Registros de eventos"
            elif has_complex_objects:
                return "Documentos complejos"
            else:
                return "Documentos estándar"
                
        except Exception as e:
            print(f"Error al detectar tipo de contenido: {e}")
            return "Desconocido"
    
    def get_field_description(self, field_name):
        """Proporciona una descripción para campos comunes"""
        field_lower = field_name.lower()
        
        # Campos de identificación
        if field_name == '_id':
            return "Identificador único del documento"
        elif 'id' in field_lower or 'uuid' in field_lower:
            return "Identificador único"
            
        # Campos comunes de usuario
        elif field_lower in ['name', 'nombre']:
            return "Nombre"
        elif field_lower in ['email', 'correo', 'mail']:
            return "Correo electrónico"
        elif field_lower in ['phone', 'telefono', 'tel', 'movil']:
            return "Número de teléfono"
        elif field_lower in ['address', 'direccion']:
            return "Dirección postal"
        elif field_lower in ['password', 'contrasena', 'clave']:
            return "Contraseña (cifrada)"
        elif field_lower in ['role', 'rol']:
            return "Rol o nivel de permisos"
            
        # Campos de ubicación
        elif field_lower in ['location', 'ubicacion', 'coordinates', 'coordenadas']:
            return "Datos de ubicación geográfica"
            
        # Campos temporales
        elif 'date' in field_lower or 'fecha' in field_lower:
            return "Fecha"
        elif 'time' in field_lower or 'hora' in field_lower:
            return "Hora"
        elif field_lower in ['created_at', 'fecha_creacion', 'creation_date']:
            return "Fecha de creación"
        elif field_lower in ['updated_at', 'fecha_actualizacion', 'last_modified']:
            return "Fecha de última modificación"
            
        # Campos de producto
        elif field_lower in ['price', 'precio']:
            return "Precio"
        elif field_lower in ['cost', 'costo']:
            return "Costo"
        elif field_lower in ['description', 'descripcion']:
            return "Descripción"
        elif field_lower in ['category', 'categoria']:
            return "Categoría"
        elif field_lower in ['stock', 'inventory', 'inventario']:
            return "Cantidad en inventario"
            
        # Metadatos
        elif field_lower in ['type', 'tipo']:
            return "Tipo de documento"
        elif field_lower in ['status', 'estado']:
            return "Estado"
        elif field_lower in ['tags', 'etiquetas']:
            return "Etiquetas o categorías"
            
        # Otros campos comunes
        elif field_lower in ['active', 'activo']:
            return "Estado de activación"
        elif field_lower in ['comments', 'comentarios']:
            return "Comentarios"
        elif field_lower in ['image', 'imagen', 'photo', 'foto']:
            return "Ruta de imagen o datos binarios"
            
        # Relaciones
        elif field_lower.endswith('_id'):
            related_entity = field_lower[:-3].replace('_', ' ')
            return f"Referencia a {related_entity}"
            
        # Valor predeterminado
        return "Campo de datos"
    
    def refresh_collection_preview(self):
        """Actualiza la vista previa de acuerdo al tipo de contenido seleccionado"""
        if not hasattr(self, 'preview_stack') or not self.current_collection:
            return
            
        try:
            collection_name = self.current_collection
            collection = self.db[collection_name]
            
            # Obtener tipo de vista previa seleccionado
            preview_type = self.preview_type_selector.currentText()
            preview_index = self.preview_type_selector.currentIndex()
            
            # Limpiar widgets de vista previa existentes
            if self.preview_stack.count() > 0:
                # Obtener widgets actuales
                table_preview = self.preview_stack.widget(0)
                chart_preview = self.preview_stack.widget(1)
                json_preview = self.preview_stack.widget(2)
                text_preview = self.preview_stack.widget(3)
                
                # Limpiar cada widget
                if isinstance(table_preview, QTableWidget):
                    table_preview.setRowCount(0)
                    table_preview.setColumnCount(0)
                
                if isinstance(json_preview, QTextEdit):
                    json_preview.clear()
                
                if isinstance(text_preview, QTextEdit):
                    text_preview.clear()
            
            # Obtener documentos para la vista previa
            preview_docs = list(collection.find().limit(20))
            if not preview_docs:
                # No hay documentos para mostrar
                message = "No hay documentos para mostrar en la vista previa"
                
                if preview_type == "Tabla":
                    table_preview = self.preview_stack.widget(0)
                    table_preview.setRowCount(1)
                    table_preview.setColumnCount(1)
                    table_preview.setItem(0, 0, QTableWidgetItem(message))
                elif preview_type == "JSON":
                    json_preview = self.preview_stack.widget(2)
                    json_preview.setText(message)
                elif preview_type == "Texto":
                    text_preview = self.preview_stack.widget(3)
                    text_preview.setText(message)
                
                return

            # Actualizar vista previa según el tipo seleccionado
            if preview_type == "Tabla":
                table_preview = self.preview_stack.widget(0)
                
                # Prepara tabla
                all_fields = set()
                for doc in preview_docs:
                    all_fields.update(doc.keys())
                
                # Ordenar campos
                ordered_fields = ['_id'] + sorted([f for f in all_fields if f != '_id'])
                
                # Configurar tabla
                table_preview.setColumnCount(len(ordered_fields))
                table_preview.setHorizontalHeaderLabels(ordered_fields)
                table_preview.setRowCount(len(preview_docs))
                
                # Llenar datos
                for row, doc in enumerate(preview_docs):
                    for col, field in enumerate(ordered_fields):
                        if field in doc:
                            value = str(doc[field])
                            table_preview.setItem(row, col, QTableWidgetItem(value))
                
                table_preview.resizeColumnsToContents()
                
            elif preview_type == "Gráfico":
                # Para esta vista previa necesitaríamos utilizar un widget de gráficos
                # como matplotlib o pyqtgraph, pero por simplicidad, mostraremos un mensaje
                
                # Obtener o crear el widget para la vista previa de gráficos
                try:
                    chart_preview = self.preview_stack.widget(1)
                except:
                    # Si no existe, crear uno nuevo
                    chart_preview = QWidget()
                    self.preview_stack.addWidget(chart_preview)
                
                try:
                    chart_preview = self.preview_stack.widget(1)
                except:
                    # Si no existe, crear uno nuevo
                    chart_preview = QWidget()
                    self.preview_stack.addWidget(chart_preview)
                
                # Limpiar el layout existente si hay uno
                if chart_preview.layout():
                    old_layout = chart_preview.layout()
                    
                    # Eliminar todos los widgets del layout
                    while old_layout.count():
                        item = old_layout.takeAt(0)
                        if item.widget():
                            item.widget().hide()
                            item.widget().deleteLater()
                        elif item.layout():
                            sub_layout = item.layout()
                            while sub_layout.count():
                                sub_item = sub_layout.takeAt(0)
                                if sub_item.widget():
                                    sub_item.widget().deleteLater()
                    
                    # Desasociar el layout antiguo
                    QWidget().setLayout(old_layout)
                
                # Crear layout para el mensaje y agregarlo
                chart_layout = QVBoxLayout(chart_preview)
                message_label = QLabel("Vista de gráfico no disponible. Esta funcionalidad requiere módulos adicionales.")
                chart_layout.addWidget(message_label)
                
            elif preview_type == "JSON":
                json_preview = self.preview_stack.widget(2)
                
                # Preparar texto JSON bien formateado
                import json
                
                # Convertir documentos a JSON
                json_text = json.dumps(preview_docs, default=str, indent=2)
                json_preview.setText(json_text)
                
            elif preview_type == "Texto":
                text_preview = self.preview_stack.widget(3)
                
                # Preparar representación de texto simple
                text_content = ""
                for i, doc in enumerate(preview_docs):
                    text_content += f"Documento {i+1}:\n"
                    for key, value in doc.items():
                        text_content += f"  {key}: {value}\n"
                    text_content += "\n"
                
                text_preview.setText(text_content)
            
            # Cambiar al widget correspondiente
            self.preview_stack.setCurrentIndex(preview_index)
            
        except Exception as e:
            print(f"Error al actualizar vista previa: {e}")
            
            # Mostrar error en el widget activo
            current_widget = self.preview_stack.currentWidget()
            if isinstance(current_widget, QTextEdit):
                current_widget.setText(f"Error al generar vista previa: {str(e)}")
            elif isinstance(current_widget, QTableWidget):
                current_widget.setRowCount(1)
                current_widget.setColumnCount(1)
                current_widget.setItem(0, 0, QTableWidgetItem(f"Error: {str(e)}"))
    
    def load_access_history(self, collection_name):
        """Cargar historial de acceso de la colección"""
        try:
            self.meta_access_table.setRowCount(0)
            
            # Intentar obtener historial de acceso desde logs o auditoría
            access_logs = []
            
            # Verificar si existe una colección de auditoría
            if "audit_log" in self.db.list_collection_names():
                # Buscar registros relacionados con esta colección
                logs = list(self.db["audit_log"].find(
                    {"collection": collection_name}
                ).sort("timestamp", -1).limit(5))
                
                if logs:
                    access_logs = logs
            
            # Si no hay logs de auditoría, crear algunos datos de muestra
            if not access_logs:
                # Crear un historial de acceso de muestra
                import datetime
                
                owner_info = self.find_collection_owner(collection_name)
                owner_name = owner_info.get("nombre", "Administrador")
                
                # Datos de muestra para historial de acceso
                access_logs = [
                    {"usuario": "admin", "accion": "Consulta", "fecha": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")},
                    {"usuario": "sistema", "accion": "Actualización", "fecha": (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%d/%m/%Y %H:%M")},
                    {"usuario": owner_name, "accion": "Creación", "fecha": self.meta_created_date.text()}
                ]
            
            # Añadir los registros a la tabla
            self.meta_access_table.setRowCount(len(access_logs))
            for i, log in enumerate(access_logs):
                self.meta_access_table.setItem(i, 0, QTableWidgetItem(str(log.get("usuario", log.get("user", "N/A")))))
                self.meta_access_table.setItem(i, 1, QTableWidgetItem(str(log.get("accion", log.get("action", "N/A")))))
                self.meta_access_table.setItem(i, 2, QTableWidgetItem(str(log.get("fecha", log.get("timestamp", "N/A")))))
            
            self.meta_access_table.resizeColumnsToContents()
            
        except Exception as e:
            print(f"Error al cargar historial de acceso: {e}")
    def get_all_collection_owners(self):
        """Get owner information for all collections in the database"""
        owners_cache = {}
        
        try:
            if not self.db:
                return {}
                
            # Get all collections
            collections = self.db.list_collection_names()
            
            # Find owners for each collection
            for collection_name in collections:
                owner_info = self.find_collection_owner(collection_name)
                owners_cache[collection_name] = owner_info
                
            return owners_cache
            
        except Exception as e:
            print(f"Error getting all collection owners: {e}")
            return {}
    
    def find_collection_owner(self, collection_name):
        """Encuentra el propietario de una colección buscando en metadatos y documentos"""
        owner_info = {
            "nombre": "Desconocido",
            "email": "N/A",
            "departamento": "N/A",
            "cargo": "N/A",
            "telefono": "N/A"
        }
        
        try:
            collection = self.db[collection_name]
            
            # Estrategia 1: Buscar en documento de metadatos específico
            meta_doc = collection.find_one({"type": "metadata"}) or collection.find_one({"type": "collection_info"})
            if meta_doc:
                if "owner" in meta_doc:
                    owner_info["nombre"] = meta_doc["owner"]
                elif "creator" in meta_doc:
                    owner_info["nombre"] = meta_doc["creator"]
                
                owner_info["email"] = meta_doc.get("email", meta_doc.get("owner_email", "N/A"))
                owner_info["departamento"] = meta_doc.get("department", meta_doc.get("owner_department", "N/A"))
                owner_info["cargo"] = meta_doc.get("role", meta_doc.get("owner_role", "N/A"))
                owner_info["telefono"] = meta_doc.get("phone", meta_doc.get("owner_phone", "N/A"))
                
                # Si encontramos información del propietario, retornar
                if owner_info["nombre"] != "Desconocido":
                    return owner_info
            
            # Estrategia 2: Buscar en cualquier documento que tenga un campo owner/creator
            owner_doc = (collection.find_one({"owner": {"$exists": True}}) or 
                         collection.find_one({"created_by": {"$exists": True}}) or 
                         collection.find_one({"creator": {"$exists": True}}))
            
            if owner_doc:
                if "owner" in owner_doc:
                    owner_val = owner_doc["owner"]
                    if isinstance(owner_val, dict):
                        owner_info["nombre"] = owner_val.get("name", str(owner_val))
                        owner_info["email"] = owner_val.get("email", "N/A")
                        owner_info["departamento"] = owner_val.get("department", "N/A")
                        owner_info["cargo"] = owner_val.get("role", "N/A")
                    else:
                        owner_info["nombre"] = str(owner_val)
                elif "created_by" in owner_doc:
                    owner_info["nombre"] = str(owner_doc["created_by"])
                elif "creator" in owner_doc:
                    owner_info["nombre"] = str(owner_doc["creator"])
                
                return owner_info
            
            # Estrategia 3: Buscar en colección de usuarios para ver si alguien tiene permisos de propietario
            if "users" in self.db.list_collection_names():
                owner_user = self.db["users"].find_one({"permissions.collections": collection_name, "permissions.role": "owner"})
                if owner_user:
                    owner_info["nombre"] = owner_user.get("name", owner_user.get("username", "Usuario"))
                    owner_info["email"] = owner_user.get("email", "N/A")
                    owner_info["departamento"] = owner_user.get("department", owner_user.get("departamento", "N/A"))
                    owner_info["cargo"] = owner_user.get("role", owner_user.get("cargo", "N/A"))
                
            return owner_info
        except Exception as e:
            print(f"Error al buscar propietario de la colección: {e}")
            return owner_info
    
    def create_collection(self):
        """Crear una nueva colección en la base de datos"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        dialog = CreateCollectionDialog(self)
        if dialog.exec():
            collection_name = dialog.name_input.text().strip()
            
            if not collection_name:
                QMessageBox.warning(self, "Advertencia", "El nombre de la colección no puede estar vacío")
                return
                
            try:
                # Create the collection
                self.db.create_collection(collection_name)
                
                # Update the UI
                self.show_collections()
                self.update_database_stats()
                self.show_status_message(f"Collection '{collection_name}' created successfully")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create collection: {str(e)}")
                self.show_status_message(f"Error: {str(e)}", error=True)
    
    def drop_collection(self):
        """Drop a collection from the database"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Select collection to drop
            collections = self.db.list_collection_names()
                
            if not collections:
                QMessageBox.information(self, "Información", "No hay colecciones para eliminar")
                return
                
            dialog = DropCollectionDialog(self, collections)
            if dialog.exec():
                collection_name = dialog.get_selected_collection()
                
                # Confirm again
                confirm = QMessageBox.question(
                    self, 
                    "Confirmar Eliminación", 
                    f"¿Está seguro de que desea eliminar la colección '{collection_name}'?\n¡Esta acción no se puede deshacer!",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if confirm == QMessageBox.StandardButton.Yes:
                    try:
                        self.db.drop_collection(collection_name)
                        
                        # Update UI
                        self.show_collections()
                        self.update_database_stats()
                        self.show_status_message(f"Collection '{collection_name}' dropped successfully")
                        
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to drop collection: {str(e)}")
                        self.show_status_message(f"Error: {str(e)}", error=True)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process collection drop: {str(e)}")
    
    def execute_query(self):
        """Execute a MongoDB query from the query editor"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        query_text = self.query_editor.toPlainText().strip()
        
        if not query_text:
            self.results_view.setPlainText("No query to execute")
            return
            
        # Very basic query parser
        # This is a simplified implementation - in a real app, you would need a more robust parser
        try:
            # Parse the query text to extract collection and operation
            import re
            import json
            
            # Try to match collection and method
            match = re.search(r'db\.(\w+)\.(\w+)\((.*)\)', query_text)
            
            if not match:
                self.results_view.setPlainText("Invalid query format. Use: db.collection.operation(params)")
                return
                
            collection_name = match.group(1)
            operation = match.group(2)
            params_str = match.group(3).strip()
            
            # Check if collection exists
            if collection_name not in self.db.list_collection_names():
                self.results_view.setPlainText(f"Collection '{collection_name}' does not exist")
                return
            
            collection = self.db[collection_name]
            
            # Handle different operations
            if operation == "find":
                # Parse query and projection parameters
                if params_str:
                    try:
                        # Extract query and projection parameters
                        if "," in params_str:
                            query_part, projection_part = params_str.split(",", 1)
                            query = json.loads(query_part)
                            projection = json.loads(projection_part)
                            results = collection.find(query, projection)
                        else:
                            query = json.loads(params_str)
                            results = collection.find(query)
                    except json.JSONDecodeError:
                        self.results_view.setPlainText(f"Invalid JSON in query parameters: {params_str}")
                        return
                else:
                    # Empty params means find all
                    results = collection.find()
                
                # Format results
                results_list = list(results)
                if results_list:
                    formatted_results = json.dumps(results_list, indent=2, default=str)
                    self.results_view.setPlainText(formatted_results)
                    self.show_status_message(f"Found {len(results_list)} documents")
                else:
                    self.results_view.setPlainText("No documents found matching the query")
                    self.show_status_message("No documents found")
                    
            elif operation == "insertOne":
                try:
                    document = json.loads(params_str)
                    result = collection.insert_one(document)
                    self.results_view.setPlainText(f"Document inserted with ID: {result.inserted_id}")
                    self.show_status_message("Document inserted successfully")
                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON document: {params_str}")
                
            elif operation == "insertMany":
                try:
                    documents = json.loads(params_str)
                    if not isinstance(documents, list):
                        self.results_view.setPlainText("insertMany requires an array of documents")
                        return
                    result = collection.insert_many(documents)
                    self.results_view.setPlainText(f"Inserted {len(result.inserted_ids)} documents")
                    self.show_status_message(f"Inserted {len(result.inserted_ids)} documents")
                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON array: {params_str}")
                
            elif operation == "updateOne" or operation == "updateMany":
                try:
                    if "," not in params_str:
                        self.results_view.setPlainText(f"{operation} requires filter and update documents")
                        return
                        
                    filter_part, update_part = params_str.split(",", 1)
                    filter_doc = json.loads(filter_part)
                    update_doc = json.loads(update_part)
                    
                    if operation == "updateOne":
                        result = collection.update_one(filter_doc, update_doc)
                        matched = result.matched_count
                        modified = result.modified_count
                    else:
                        result = collection.update_many(filter_doc, update_doc)
                        matched = result.matched_count
                        modified = result.modified_count
                        
                    self.results_view.setPlainText(f"Matched: {matched}, Modified: {modified}")
                    self.show_status_message(f"Updated {modified} of {matched} matching documents")
                    
                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON in parameters: {params_str}")
                
            elif operation == "deleteOne" or operation == "deleteMany":
                try:
                    filter_doc = json.loads(params_str)
                    
                    if operation == "deleteOne":
                        result = collection.delete_one(filter_doc)
                        deleted = result.deleted_count
                    else:
                        result = collection.delete_many(filter_doc)
                        deleted = result.deleted_count
                        
                    self.results_view.setPlainText(f"Deleted {deleted} document(s)")
                    self.show_status_message(f"Deleted {deleted} document(s)")
                    
                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON filter: {params_str}")
                
            elif operation == "aggregate":
                try:
                    pipeline = json.loads(params_str)
                    if not isinstance(pipeline, list):
                        self.results_view.setPlainText("Aggregate requires a pipeline array")
                        return
                        
                    results = list(collection.aggregate(pipeline))
                    if results:
                        formatted_results = json.dumps(results, indent=2, default=str)
                        self.results_view.setPlainText(formatted_results)
                    else:
                        self.results_view.setPlainText("No results from aggregation pipeline")
                    self.show_status_message(f"Aggregation returned {len(results)} results")
                    
                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON pipeline: {params_str}")
            
            else:
                self.results_view.setPlainText(f"Operation not supported: {operation}\n\nSupported operations: find, insertOne, insertMany, updateOne, updateMany, deleteOne, deleteMany, aggregate")
                
        except Exception as e:
            self.results_view.setPlainText(f"Error executing query: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    
    def show_about(self):
        """Show information about the application"""
        about_text = """
<h2>Gestor de Base de Datos MongoDB</h2>
<p>Versión 1.0.0</p>
<p>Una aplicación GUI multiplataforma para la gestión de bases de datos MongoDB.</p>
<p>Características:</p>
<ul>
    <li>Conectar a bases de datos MongoDB</li>
    <li>Ver y gestionar colecciones</li>
    <li>Ejecutar consultas MongoDB</li>
    <li>Importar y exportar datos</li>
    <li>Gestión de usuarios y permisos</li>
    <li>Interfaz moderna e intuitiva</li>
</ul>
<p>Creado por Eugenio de Frutos con ❤️</p>
<p>&copy; 2025 Eugenio de Frutos - Todos los derechos reservados</p>
"""
        
        QMessageBox.about(self, "Acerca de Gestor de Base de Datos MongoDB", about_text)
    
    def show_status_message(self, message, timeout=5000, error=False):
        """Show a message in the status bar
        
        Args:
            message (str): Message to display
            timeout (int, optional): How long to show message in ms. Defaults to 5000.
            error (bool, optional): If True, format as error. Defaults to False.
        """
        if error:
            self.statusBar().setStyleSheet("QStatusBar{color:red;font-weight:bold;}")
        else:
            self.statusBar().setStyleSheet("")
            
        # Show message and restore after timeout
        self.statusBar().showMessage(message, timeout)
        
    def apply_style(self):
        """Apply consistent styling to the window and widgets"""
        # Set window icon
        # self.setWindowIcon(QIcon("icon.png"))  # Uncomment and provide icon path if available
        
        # Set font
        app_font = QFont("Segoe UI", 9)  # Modern font
        QApplication.setFont(app_font)
        
        # Definir colores para elementos de UI
        bg_color = "#1d1d1d"  # Color de fondo oscuro
        fg_color = "#ffffff"  # Color de texto claro
        
        # Set stylesheet for the entire window
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
            }
            
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #4a90e2;
                color: white;
            }
            
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            
            QPushButton:hover {
                background-color: #3a80d2;
            }
            
            QPushButton:pressed {
                background-color: #2a70c2;
            }
            
            QTextEdit, QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            
            QTreeView, QTableWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 4px;
                border: 1px solid #cccccc;
                font-weight: bold;
            }
            
            QStatusBar {
                background-color: #f0f0f0;
                border-top: 1px solid #cccccc;
            }
            
            QLabel {
                color: #333333;
            }
        """)
        # Aplicar estilos para tablas y editores
        # Aplicar estilos para tablas y editores
        # Aplicar estilos para tablas y editores
        if hasattr(self, 'data_table'):
            self.data_table.setAlternatingRowColors(True)
        if hasattr(self, 'results_view'):
            self.results_view.setStyleSheet(f"QTextEdit {{ background-color: {bg_color}; color: {fg_color}; }}")
        
    def show_databases(self):
        """Mostrar todas las bases de datos disponibles"""
        if self.client is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            databases = self.client.list_database_names()
            
            # Crear diálogo para mostrar las bases de datos
            dialog = QDialog(self)
            dialog.setWindowTitle("Bases de Datos Disponibles")
            dialog.resize(400, 300)
            
            layout = QVBoxLayout(dialog)
            
            # Crear lista
            from PyQt6.QtWidgets import QListWidget
            db_list = QListWidget()
            db_list.addItems(databases)
            layout.addWidget(db_list)
            
            # Añadir botones
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            switch_button = QPushButton("Cambiar a Seleccionada")
            button_box.addButton(switch_button, QDialogButtonBox.ButtonRole.ActionRole)
            
            switch_button.clicked.connect(lambda: self.switch_to_database(db_list.currentItem().text(), dialog))
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al mostrar bases de datos: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    
    def switch_database(self):
        """Mostrar dialog para cambiar a otra base de datos"""
        if self.client is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Get database list from MongoDB
            all_dbs = self.client.list_database_names()
            
            # Filter out system databases
            db_list = [db for db in all_dbs if db not in ['admin', 'local', 'config']]
            
            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Cambiar Base de Datos")
            dialog.resize(400, 300)
            
            layout = QVBoxLayout(dialog)
            
            # Header
            header = QLabel("Seleccione una base de datos para cambiar:")
            layout.addWidget(header)
            
            # Database list
            db_list_widget = QListWidget()
            db_list_widget.addItems(db_list)
            layout.addWidget(db_list_widget)
            
            # Buttons
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            switch_button = QPushButton("Cambiar")
            button_box.addButton(switch_button, QDialogButtonBox.ButtonRole.AcceptRole)
            
            # Connect signals
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            switch_button.clicked.connect(lambda: self.switch_to_database(db_list_widget.currentItem().text(), dialog))
            
            layout.addWidget(button_box)
            
            # Execute dialog
            if dialog.exec() == QDialog.DialogCode.Accepted and db_list_widget.currentItem():
                self.switch_to_database(db_list_widget.currentItem().text())
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cambiar de base de datos: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
    def switch_to_database(self, db_name, dialog=None):
        """Cambiar a una base de datos específica"""
        if self.client is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión al servidor MongoDB")
            if dialog:
                dialog.reject()
            return
            
        if db_name == self.database_name:
            QMessageBox.information(self, "Información", f"Ya está conectado a la base de datos '{db_name}'")
            if dialog:
                dialog.accept()
            return
            
        try:
            # Validar que la base de datos existe
            print(f"Comprobando si la base de datos '{db_name}' existe...")
            available_dbs = self.client.list_database_names()
            if db_name not in available_dbs:
                QMessageBox.warning(self, "Advertencia", f"La base de datos '{db_name}' no existe o no es accesible")
                if dialog:
                    dialog.reject()
                return
                
            # Guardar estado de la conexión actual
            current_db_name = self.database_name
            
            # Cambiar base de datos
            print(f"Cambiando de base de datos: {current_db_name} → {db_name}")
            self.database_name = db_name
            self.db = self.client[db_name]
            
            # Verificar que podemos listar colecciones (prueba de acceso)
            try:
                collections = self.db.list_collection_names()
                print(f"Acceso verificado a '{db_name}', encontradas {len(collections)} colecciones")
            except Exception as access_error:
                print(f"Error al acceder a la base de datos '{db_name}': {access_error}")
                # Restaurar estado anterior
                self.database_name = current_db_name
                self.db = self.client[current_db_name]
                QMessageBox.critical(self, "Error", f"No se pudo acceder a la base de datos '{db_name}': {str(access_error)}")
                self.show_status_message(f"Error: {str(access_error)}", error=True)
                if dialog:
                    dialog.reject()
                return
            
            # Actualizar interfaz
            try:
                # Actualizar etiqueta de estado de conexión
                self.connection_status_label.setText(f"Conectado a: {db_name}")
                
                # Habilitar la pestaña de colecciones
                if not self.tab_widget.isTabEnabled(1):
                    self.tab_widget.setTabEnabled(1, True)
                
                # Cambiar a la pestaña de colecciones para mostrar el nuevo contenido
                self.tab_widget.setCurrentIndex(1)
                
                # Mostrar las colecciones en la nueva base de datos
                self.show_collections()
                
                # Actualizar estadísticas
                self.update_database_stats()
                
                # Mostrar mensaje de éxito
                self.show_status_message(f"Cambiado a la base de datos: {db_name}")
                
                # Cerrar diálogo si se proporcionó
                if dialog:
                    dialog.accept()
                    
            except Exception as ui_error:
                print(f"Error al actualizar la interfaz para '{db_name}': {ui_error}")
                self.show_status_message(f"Conexión cambiada, pero hubo errores al actualizar la interfaz", error=True)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cambiar de base de datos: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    def show_global_stats(self):
        """Ver estadísticas globales de MongoDB"""
        if self.client is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
        
        try:
            # Obtener estado del servidor
            status = self.client.admin.command("serverStatus")
            
            # Extraer estadísticas relevantes
            version = status.get("version", "Desconocida")
            uptime = status.get("uptime", 0)
            connections = status.get("connections", {})
            current_connections = connections.get("current", 0)
            available_connections = connections.get("available", 0)
            
            # Obtener lista de bases de datos y tamaños
            databases = []
            total_size = 0
            
            try:
                # Filtrar bases de datos del sistema
                database_names = self.client.list_database_names()
                filtered_dbs = [db for db in database_names if db not in ['admin', 'local', 'config']]
                
                for db_name in filtered_dbs:
                    try:
                        db = self.client[db_name]
                        stats = db.command("dbStats")
                        size_mb = stats.get("dataSize", 0) / (1024 * 1024)
                        total_size += size_mb
                        databases.append((db_name, f"{size_mb:.2f} MB"))
                    except Exception as db_error:
                        print(f"Error al obtener estadísticas para {db_name}: {db_error}")
                        databases.append((db_name, "Error al obtener tamaño"))
            except Exception as list_error:
                print(f"Error al listar bases de datos: {list_error}")
                QMessageBox.warning(self, "Advertencia", f"Error al listar bases de datos: {str(list_error)}")
            
            # Crear diálogo para mostrar estadísticas
            dialog = QDialog(self)
            dialog.setWindowTitle("Estadísticas Globales de MongoDB")
            dialog.resize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            # Sección de información del servidor
            server_info = QLabel("Información del Servidor")
            server_info.setStyleSheet("font-size: 16px; font-weight: bold;")
            layout.addWidget(server_info)
            
            info_text = QLabel(f"""
Versión de MongoDB: {version}
Tiempo de actividad: {uptime/86400:.1f} días
Conexiones actuales: {current_connections}
Conexiones disponibles: {available_connections}
Total de bases de datos: {len(databases)}""")
            info_text.setStyleSheet("background-color: #f5f5f5; padding: 10px; border-radius: 5px;")
            layout.addWidget(info_text)
            
            # Database list section
            db_label = QLabel("Bases de Datos")
            db_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 15px;")
            layout.addWidget(db_label)
            # Table for databases
            from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
            db_table = QTableWidget()
            db_table.setColumnCount(2)
            db_table.setHorizontalHeaderLabels(["Base de Datos", "Tamaño"])
            db_table.setRowCount(len(databases))
            
            for i, (db_name, size) in enumerate(databases):
                db_table.setItem(i, 0, QTableWidgetItem(db_name))
                db_table.setItem(i, 1, QTableWidgetItem(size))
                
            db_table.resizeColumnsToContents()
            layout.addWidget(db_table)
            
            # Add close button
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al recuperar estadísticas del servidor: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    def list_databases_by_owner(self):
        """Listar bases de datos agrupadas por propietario con información detallada"""
        if self.client is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            print("Iniciando listado de bases de datos por propietario...")
            # Obtener todas las bases de datos
            databases = self.client.list_database_names()
            print(f"Encontradas {len(databases)} bases de datos en total")
            
            # Diccionario para agrupar por propietario
            owners_dict = {}
            # Diccionario para almacenar información detallada de propietarios
            owner_details = {}
            
            # Para cada base de datos, intentar encontrar información del propietario
            for db_name in databases:
                # Excluir bases de datos del sistema
                if db_name in ['admin', 'local', 'config']:
                    print(f"Saltando base de datos del sistema: {db_name}")
                    continue
                    
                # Agregar al propietario "Aplicaciones" por defecto
                owner = "Aplicaciones"
                size_str = "Calculando..."
                owner_info = {
                    "nombre": "Aplicaciones",
                    "email": "N/A",
                    "departamento": "N/A",
                    "cargo": "N/A",
                    "telefono": "N/A"
                }
                
                try:
                    db = self.client[db_name]
                    
                    # Buscar información de propietario en colecciones relevantes
                    try:
                        collection_names = db.list_collection_names()
                        print(f"Analizando propietario para {db_name} con {len(collection_names)} colecciones")
                        
                        # Intentar obtener información del propietario desde metadatos
                        if 'metadata' in collection_names:
                            metadata = db.metadata.find_one({'type': 'owner'})
                            if metadata and 'owner' in metadata:
                                owner = metadata['owner']
                                print(f"Propietario encontrado en metadata: {owner}")
                                # Extraer información adicional si está disponible
                                owner_info["nombre"] = owner
                                owner_info["email"] = metadata.get('email', 'N/A')
                                owner_info["departamento"] = metadata.get('departamento', 'N/A')
                                owner_info["cargo"] = metadata.get('cargo', 'N/A')
                                owner_info["telefono"] = metadata.get('telefono', 'N/A')
                        # Alternativamente, buscar en las colecciones de propietarios/admin
                        elif 'owners' in collection_names:
                            owner_doc = db.owners.find_one({})
                            if owner_doc and 'name' in owner_doc:
                                owner = owner_doc['name']
                                print(f"Propietario encontrado en owners: {owner}")
                                owner_info["nombre"] = owner
                                owner_info["email"] = owner_doc.get('email', 'N/A')
                                owner_info["departamento"] = owner_doc.get('department', 'N/A')
                                owner_info["cargo"] = owner_doc.get('position', 'N/A')
                                owner_info["telefono"] = owner_doc.get('phone', 'N/A')
                        elif 'admins' in collection_names:
                            admin_doc = db.admins.find_one({})
                            if admin_doc and 'name' in admin_doc:
                                owner = admin_doc['name']
                                print(f"Propietario encontrado en admins: {owner}")
                                owner_info["nombre"] = owner
                                owner_info["email"] = admin_doc.get('email', 'N/A')
                                owner_info["departamento"] = admin_doc.get('department', 'N/A')
                                owner_info["cargo"] = admin_doc.get('position', 'N/A')
                                owner_info["telefono"] = admin_doc.get('phone', 'N/A')
                        elif 'usuarios' in collection_names:
                            user_doc = db.usuarios.find_one({'admin': True})
                            if user_doc and 'nombre' in user_doc:
                                owner = user_doc['nombre']
                                print(f"Propietario encontrado en usuarios: {owner}")
                                owner_info["telefono"] = user_doc.get('phone', 'N/A')
                        elif 'users' in collection_names:
                            user_doc = db.users.find_one({'role': 'admin'})
                            if user_doc and 'name' in user_doc:
                                owner = user_doc['name']
                                print(f"Propietario encontrado en users: {owner}")
                                owner_info["nombre"] = owner
                                owner_info["email"] = user_doc.get('email', 'N/A')
                                owner_info["departamento"] = user_doc.get('department', 'N/A')
                                owner_info["cargo"] = user_doc.get('position', 'N/A')
                                owner_info["telefono"] = user_doc.get('phone', 'N/A')
                
                    except Exception as owner_error:
                        print(f"Error al obtener propietario para {db_name}: {owner_error}")
                    
                    # Obtener tamaño de la base de datos
                    try:
                        stats = db.command("dbStats")
                        size_mb = stats.get("dataSize", 0) / (1024 * 1024)
                        size_str = f"{size_mb:.2f} MB"
                        print(f"Tamaño de {db_name}: {size_str}")
                    except Exception as stats_error:
                        print(f"Error al obtener estadísticas para {db_name}: {stats_error}")
                        size_str = "No disponible"
                        
                except Exception as db_error:
                    print(f"Error al acceder a la base de datos {db_name}: {db_error}")
                    size_str = "Error de acceso"
                
                # Agregar a diccionario agrupado por propietario
                if owner not in owners_dict:
                    owners_dict[owner] = []
                    owner_details[owner] = owner_info
                
                owners_dict[owner].append((db_name, size_str))
                if owner not in owners_dict:
                    owners_dict[owner] = []
                
                owners_dict[owner].append((db_name, size_str))
            
            # Si no hay bases de datos para mostrar
            if not owners_dict:
                QMessageBox.information(self, "Información", "No hay bases de datos disponibles para mostrar")
                return
                
            # Crear un diálogo para mostrar las bases de datos agrupadas por propietario
            dialog = QDialog(self)
            dialog.setWindowTitle("Bases de Datos por Propietario")
            dialog.resize(700, 500)
            
            layout = QVBoxLayout(dialog)
            
            # Etiqueta de información
            info_label = QLabel(f"Mostrando bases de datos agrupadas por propietario")
            info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(info_label)
            
            # Crear un widget con pestañas para cada propietario
            tab_widget = QTabWidget()
            
            # Para cada propietario, crear una pestaña
            for owner, databases in owners_dict.items():
                owner_widget = QWidget()
                owner_layout = QVBoxLayout(owner_widget)
                
                # Mostrar información detallada del propietario
                owner_info = owner_details.get(owner, {
                    "nombre": owner,
                    "email": "N/A",
                    "departamento": "N/A",
                    "cargo": "N/A",
                    "telefono": "N/A"
                })
                
                # Crear panel de información de propietario
                info_frame = QFrame()
                info_frame.setFrameShape(QFrame.Shape.StyledPanel)
                info_frame.setStyleSheet("background-color: #f0f7ff; border-radius: 5px; padding: 10px;")
                info_layout = QVBoxLayout(info_frame)
                
                # Título de información de propietario
                title_label = QLabel(f"<h3>Información del Propietario: {owner_info['nombre']}</h3>")
                info_layout.addWidget(title_label)
                
                # Detalles de contacto en formato de tabla
                contact_layout = QFormLayout()
                contact_layout.addRow("<b>Correo Electrónico:</b>", QLabel(owner_info["email"]))
                contact_layout.addRow("<b>Departamento:</b>", QLabel(owner_info["departamento"]))
                contact_layout.addRow("<b>Cargo:</b>", QLabel(owner_info["cargo"]))
                contact_layout.addRow("<b>Teléfono:</b>", QLabel(owner_info["telefono"]))
                info_layout.addLayout(contact_layout)
                
                # Añadir panel de información al layout principal
                owner_layout.addWidget(info_frame)
                
                # Crear tabla para las bases de datos
                db_label = QLabel("<h4>Bases de Datos Pertenecientes:</h4>")
                owner_layout.addWidget(db_label)
                
                table = QTableWidget()
                table.setColumnCount(3)
                table.setHorizontalHeaderLabels(["Base de Datos", "Tamaño", "Colecciones"])
                table.setRowCount(len(databases))
                
                # Llenar tabla con las bases de datos del propietario
                for i, (db_name, size_str) in enumerate(databases):
                    table.setItem(i, 0, QTableWidgetItem(db_name))
                    table.setItem(i, 1, QTableWidgetItem(size_str))
                    
                    # Contar colecciones
                    try:
                        collection_count = len(self.client[db_name].list_collection_names())
                        table.setItem(i, 2, QTableWidgetItem(str(collection_count)))
                    except:
                        table.setItem(i, 2, QTableWidgetItem("N/A"))
                
                table.resizeColumnsToContents()
                owner_layout.addWidget(table)
                # Añadir botones de acción
                button_layout = QHBoxLayout()
                
                switch_button = QPushButton("Cambiar a Base de Datos")
                switch_button.setStyleSheet("background-color: #4a90e2; color: white;")
                switch_button.clicked.connect(lambda checked, t=table: self.switch_to_database_from_table(t))
                button_layout.addWidget(switch_button)
                
                details_button = QPushButton("Ver Detalles")
                details_button.clicked.connect(lambda checked, t=table: self.show_database_details(t))
                button_layout.addWidget(details_button)
                
                # Añadir el layout de botones al layout del widget
                owner_layout.addLayout(button_layout)
                
                # Añadir la pestaña
                tab_widget.addTab(owner_widget, owner)
            
            layout.addWidget(tab_widget)
            
            # Botón para cerrar el diálogo
            close_button = QPushButton("Cerrar")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al listar propietarios de tablas: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
    def list_table_owners(self):
        """Listar propietarios de tablas/colecciones específicas en todas las bases de datos"""
        if self.client is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        progress_dialog = None
        try:
            print("Iniciando búsqueda de propietarios de tablas...")
            self.show_status_message("Analizando bases de datos y colecciones...", timeout=0)
            
            # Crear diálogo de progreso
            progress_dialog = QProgressDialog("Analizando bases de datos...", "Cancelar", 0, 100, self)
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setValue(0)
            progress_dialog.show()
            
            # Lista para almacenar información de propietarios
            owners_info = []
            
            # Obtener todas las bases de datos
            all_dbs = self.client.list_database_names()
            
            # Filtrar bases de datos del sistema
            databases = [db for db in all_dbs if db not in ['admin', 'local', 'config']]
            
            # Configurar el máximo para el diálogo de progreso
            progress_dialog.setMaximum(len(databases))
            
            # Procesar cada base de datos
            for db_idx, db_name in enumerate(databases):
                if progress_dialog.wasCanceled():
                    break
                    
                progress_dialog.setValue(db_idx)
                progress_dialog.setLabelText(f"Analizando base de datos: {db_name}")
                QApplication.processEvents()
                
                try:
                    db = self.client[db_name]
                    collections = db.list_collection_names()
                    
                    for collection_name in collections:
                        if progress_dialog.wasCanceled():
                            break
                                
                        try:
                            owner_info = {
                                "database": db_name,
                                "collection": collection_name,
                                "owner": "Desconocido",
                                "email": "N/A",
                                "department": "N/A",
                                "role": "N/A",
                                "created_date": "N/A"
                            }
                            
                            # 1. Buscar metadata de colección
                            try:
                                # Buscar en colección de metadatos específica
                                if "metadata" in collections:
                                    meta_doc = db.metadata.find_one({"collection": collection_name})
                                    if meta_doc and "owner" in meta_doc:
                                        owner_info["owner"] = meta_doc["owner"]
                                        owner_info["email"] = meta_doc.get("email", "N/A")
                                        owner_info["department"] = meta_doc.get("department", "N/A")
                                        owner_info["role"] = meta_doc.get("role", "N/A")
                                        owner_info["created_date"] = meta_doc.get("created_at", "N/A")
                            except Exception as meta_error:
                                print(f"Error al buscar metadatos para {db_name}.{collection_name}: {meta_error}")
                                continue

                            # Add owner info to the list
                            owners_info.append(owner_info)
                        except Exception as e:
                            print(f"Error al procesar colección {collection_name}: {e}")
                            continue

                    # Process events periodically to keep UI responsive
                    if db_idx % 5 == 0:
                        QApplication.processEvents()
                except Exception as db_error:
                    print(f"Error al acceder a la base de datos {db_name}: {db_error}")
                    continue
        except Exception as e:
            print(f"Error general al listar propietarios: {e}")
            QMessageBox.critical(self, "Error", f"Error al listar propietarios de tablas: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
            try:
                if progress_dialog:
                    progress_dialog.close()
            except Exception as close_error:
                print(f"Error al cerrar diálogo de progreso: {close_error}")
            
            return []

        finally:
            try:
                if progress_dialog:
                    progress_dialog.close()
            except Exception as close_error:
                print(f"Error al cerrar diálogo de progreso: {close_error}")

        return owners_info
    
    def display_owners_info(self, owners_info):
        if not owners_info:
            QMessageBox.information(self, "Información", "No se encontraron propietarios de tablas en las bases de datos")
            return
            
        try:
            # Create dialog to display results
            table_owners_dialog = QDialog(self)
            table_owners_dialog.setWindowTitle("Propietarios de Tablas/Colecciones")
            table_owners_dialog.setWindowTitle("Propietarios de Tablas/Colecciones")
            table_owners_dialog.resize(800, 600)
            
            layout = QVBoxLayout(table_owners_dialog)
            
            # Etiqueta informativa
            info_label = QLabel(f"Se encontraron {len(owners_info)} tablas/colecciones con información de propietario")
            info_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
            layout.addWidget(info_label)
            
            # Tabla de resultados
            results_table = QTableWidget()
            results_table.setColumnCount(6)
            results_table.setHorizontalHeaderLabels(["Base de Datos", "Colección", "Propietario", "Email", "Departamento", "Fecha Creación"])
            results_table.setRowCount(len(owners_info))
            
            # Llenar tabla con datos
            for i, info in enumerate(owners_info):
                results_table.setItem(i, 0, QTableWidgetItem(info["database"]))
                results_table.setItem(i, 1, QTableWidgetItem(info["collection"]))
                results_table.setItem(i, 2, QTableWidgetItem(str(info["owner"])))
                results_table.setItem(i, 3, QTableWidgetItem(str(info["email"])))
                results_table.setItem(i, 4, QTableWidgetItem(str(info["department"])))
                results_table.setItem(i, 5, QTableWidgetItem(str(info["created_date"])))
            
            # Configurar tabla para mejor visualización
            results_table.setAlternatingRowColors(True)
            results_table.setSortingEnabled(True)
            results_table.resizeColumnsToContents()
            layout.addWidget(results_table)
            
            # Opciones de filtrado
            filter_group = QGroupBox("Filtros")
            filter_layout = QHBoxLayout(filter_group)
            
            # Filtro por base de datos
            db_filter_label = QLabel("Base de Datos:")
            filter_layout.addWidget(db_filter_label)
            
            db_filter = QComboBox()
            db_filter.addItem("Todas")
            unique_dbs = sorted(set(info["database"] for info in owners_info))
            db_filter.addItems(unique_dbs)
            filter_layout.addWidget(db_filter)
            
            # Filtro por propietario
            owner_filter_label = QLabel("Propietario:")
            filter_layout.addWidget(owner_filter_label)
            
            owner_filter = QComboBox()
            owner_filter.addItem("Todos")
            unique_owners = sorted(set(str(info["owner"]) for info in owners_info))
            owner_filter.addItems(unique_owners)
            filter_layout.addWidget(owner_filter)
            
            # Botón para aplicar filtros
            apply_filter_button = QPushButton("Aplicar Filtros")
            filter_layout.addWidget(apply_filter_button)
            
            layout.addWidget(filter_group)
            
            # Función para aplicar filtros
            def apply_filters():
                selected_db = db_filter.currentText()
                selected_owner = owner_filter.currentText()
                
                # Ocultar todas las filas inicialmente
                for row in range(results_table.rowCount()):
                    results_table.setRowHidden(row, True)
                                    
                # Actualizar conteo visible
                info_label.setText(f"Aplicando filtros...")
                QApplication.processEvents()  # Permitir que la interfaz se actualice
                
                # Aplicar filtros de base de datos
                selected_db = db_filter.currentText()
                selected_owner = owner_filter.currentText()
                
                # Aplicar los filtros a cada fila
                for row in range(results_table.rowCount()):
                    db_match = selected_db == "Todas" or results_table.item(row, 0).text() == selected_db
                    owner_match = selected_owner == "Todos" or results_table.item(row, 2).text() == selected_owner
                    
                    if db_match and owner_match:
                        results_table.setRowHidden(row, False)
                
                # Contar cuántas filas están visibles después del filtro
                visible_rows = 0
                for row in range(results_table.rowCount()):
                    if not results_table.isRowHidden(row):
                        visible_rows += 1
                
                # Actualizar etiqueta con el conteo actual
                filter_message = f"Mostrando {visible_rows} de {results_table.rowCount()} resultados"
                if selected_db != "Todas":
                    filter_message += f" | Base de datos: {selected_db}"
                if selected_owner != "Todos":
                    filter_message += f" | Propietario: {selected_owner}"
                    
                info_label.setText(filter_message)
            apply_filter_button.clicked.connect(apply_filters)
            
            # Botones de acciones
            actions_layout = QHBoxLayout()
            
            view_details_button = QPushButton("Ver Detalles")
            view_details_button.clicked.connect(lambda: self.view_table_owner_details(results_table))
            actions_layout.addWidget(view_details_button)
            
            close_button = QPushButton("Cerrar")
            close_button.clicked.connect(table_owners_dialog.accept)
            actions_layout.addWidget(close_button)
            
            layout.addLayout(actions_layout)
            
            # Asegurar que el diálogo se muestre correctamente y tenga un tamaño adecuado
            table_owners_dialog.setMinimumSize(800, 600)
            
            # Mostrar diálogo
            table_owners_dialog.exec()
            
            # Mostrar mensaje de estado
            self.show_status_message(f"Se encontraron {len(owners_info)} tablas/colecciones con información de propietario")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al listar propietarios de tablas: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)

    def view_table_owner_details(self, results_table):
        """Mostrar información detallada del propietario de la tabla/colección seleccionada"""
        try:
            # Verificar si hay una fila seleccionada
            selected_row = results_table.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self, "Advertencia", "Por favor, seleccione una tabla/colección para ver sus detalles")
                return
                
            # Obtener información de la fila seleccionada
            db_name = results_table.item(selected_row, 0).text()
            collection_name = results_table.item(selected_row, 1).text()
            owner_name = results_table.item(selected_row, 2).text()
            owner_email = results_table.item(selected_row, 3).text()
            owner_dept = results_table.item(selected_row, 4).text()
            creation_date = results_table.item(selected_row, 5).text()
            
            # Crear diálogo para mostrar detalles
            detail_dialog = QDialog(self)
            detail_dialog.setWindowTitle(f"Detalles del Propietario - {collection_name}")
            detail_dialog.resize(600, 500)
            
            layout = QVBoxLayout(detail_dialog)
            
            # Información de la colección
            collection_group = QGroupBox("Información de la Colección")
            collection_layout = QFormLayout(collection_group)
            
            collection_layout.addRow("<b>Base de Datos:</b>", QLabel(db_name))
            collection_layout.addRow("<b>Colección:</b>", QLabel(collection_name))
            collection_layout.addRow("<b>Fecha de Creación:</b>", QLabel(creation_date))
            
            # Obtener estadísticas de la colección si es posible
            try:
                if db_name in self.client.list_database_names():
                    db = self.client[db_name]
                    if collection_name in db.list_collection_names():
                        # Obtener estadísticas básicas
                        count = db[collection_name].count_documents({})
                        collection_layout.addRow("<b>Número de Documentos:</b>", QLabel(str(count)))
                        
                        # Obtener información sobre índices
                        indexes = list(db[collection_name].list_indexes())
                        collection_layout.addRow("<b>Número de Índices:</b>", QLabel(str(len(indexes))))
                        
                        # Intentar obtener fecha de última modificación
                        try:
                            last_doc = db[collection_name].find_one({}, sort=[('_id', -1)])
                            if last_doc and '_id' in last_doc:
                                # Extraer timestamp de ObjectId si es posible
                                from bson.objectid import ObjectId
                                if isinstance(last_doc['_id'], ObjectId):
                                    last_modified = last_doc['_id'].generation_time.strftime('%Y-%m-%d %H:%M:%S')
                                    collection_layout.addRow("<b>Última Modificación:</b>", QLabel(last_modified))
                        except Exception as e:
                            print(f"Error al obtener última modificación: {e}")
            except Exception as stats_error:
                print(f"Error al obtener estadísticas: {stats_error}")
            
            layout.addWidget(collection_group)
            
            # Información del propietario
            owner_group = QGroupBox("Información del Propietario")
            owner_layout = QFormLayout(owner_group)
            
            owner_layout.addRow("<b>Nombre:</b>", QLabel(owner_name))
            owner_layout.addRow("<b>Email:</b>", QLabel(owner_email))
            owner_layout.addRow("<b>Departamento:</b>", QLabel(owner_dept))
            
            # Buscar información adicional del propietario en la base de datos
            try:
                additional_info = {}
                
                # Buscar en la base de datos del propietario
                if db_name in self.client.list_database_names():
                    db = self.client[db_name]
                    
                    # Buscar en colecciones típicas de usuarios/propietarios
                    collections_to_check = ['users', 'usuarios', 'admins', 'owners', 'metadata']
                    
                    for col in collections_to_check:
                        if col in db.list_collection_names():
                            # Buscar por nombre o email
                            user_doc = db[col].find_one({
                                "$or": [
                                    {"name": owner_name},
                                    {"nombre": owner_name},
                                    {"email": owner_email}
                                ]
                            })
                            
                            if user_doc:
                                # Extraer información adicional
                                if 'role' in user_doc or 'rol' in user_doc:
                                    additional_info['role'] = user_doc.get('role', user_doc.get('rol', 'N/A'))
                                if 'phone' in user_doc or 'telefono' in user_doc:
                                    additional_info['phone'] = user_doc.get('phone', user_doc.get('telefono', 'N/A'))
                                if 'position' in user_doc or 'cargo' in user_doc:
                                    additional_info['position'] = user_doc.get('position', user_doc.get('cargo', 'N/A'))
                                break
                
                # Mostrar información adicional si se encontró
                if additional_info:
                    if 'role' in additional_info:
                        owner_layout.addRow("<b>Rol:</b>", QLabel(additional_info['role']))
                    if 'position' in additional_info:
                        owner_layout.addRow("<b>Cargo:</b>", QLabel(additional_info['position']))
                    if 'phone' in additional_info:
                        owner_layout.addRow("<b>Teléfono:</b>", QLabel(additional_info['phone']))
                        
            except Exception as owner_error:
                print(f"Error al obtener información adicional del propietario: {owner_error}")
                
            layout.addWidget(owner_group)
            
            # Información de accesos y permisos
            access_group = QGroupBox("Accesos y Permisos")
            access_layout = QVBoxLayout(access_group)
            
            # Intentar buscar información de acceso en registros de auditoría
            try:
                access_logs = []
                if db_name in self.client.list_database_names():
                    db = self.client[db_name]

                    if 'audit_log' in db.list_collection_names():
                        access_logs = list(db['audit_log'].find(
                            {"collection": collection_name}
                        ).sort("timestamp", -1).limit(20))

                if access_logs:
                    access_table = QTableWidget()
                    access_table.setColumnCount(3)
                    access_table.setHorizontalHeaderLabels(["Usuario", "Acción", "Fecha"])
                    access_table.setRowCount(len(access_logs))

                    # Populate the access table with log entries
                    for i, log in enumerate(access_logs):
                        access_table.setItem(i, 0, QTableWidgetItem(str(log.get('user', log.get('usuario', 'N/A')))))
                        access_table.setItem(i, 1, QTableWidgetItem(str(log.get('action', log.get('accion', 'N/A')))))
                        access_table.setItem(i, 2, QTableWidgetItem(str(log.get('timestamp', log.get('fecha', 'N/A')))))

                    access_layout.addWidget(access_table)
                else:
                    access_layout.addWidget(QLabel("No hay registros de auditoría disponibles para esta base de datos"))

                # Add the main access group to layout
                try:
                    layout.addWidget(access_group)
                except Exception as e:
                    print(f"Error adding access group to layout: {e}")
                
                # Create button layout
                try:
                    # Botones de acción
                    button_layout = QHBoxLayout()
                    
                    # Botón para editar información (opcional)
                    edit_button = QPushButton("Editar Información")
                    edit_button.setStyleSheet("background-color: #3498db; color: white;")
                    edit_button.clicked.connect(lambda: self.edit_table_owner_info(db_name, collection_name, owner_name, detail_dialog))
                    button_layout.addWidget(edit_button)
                    
                    # Botón para cambiar a esta base de datos
                    switch_db_button = QPushButton("Cambiar a esta Base de Datos")
                    switch_db_button.clicked.connect(lambda: self.switch_to_database(db_name, detail_dialog))
                    button_layout.addWidget(switch_db_button)
                    
                    # Botón para cerrar
                    close_button = QPushButton("Cerrar")
                    close_button.clicked.connect(detail_dialog.accept)
                    button_layout.addWidget(close_button)
                    
                    layout.addLayout(button_layout)
                except Exception as e:
                    print(f"Error adding widgets to layout: {e}")
            
                # Mostrar el diálogo
                try:
                    detail_dialog.exec()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error al mostrar detalles del propietario: {str(e)}")
                    self.show_status_message(f"Error: {str(e)}", error=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al mostrar detalles del propietario: {str(e)}")
                self.show_status_message(f"Error: {str(e)}", error=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error general: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
    def edit_table_owner_info(self, db_name, collection_name, owner_name, parent_dialog=None):
        """Editar información del propietario de una tabla/colección"""
        try:
            # Cerrar diálogo padre si existe
            if parent_dialog:
                parent_dialog.accept()
                
            # Crear diálogo de edición
            edit_dialog = QDialog(self)
            edit_dialog.setWindowTitle(f"Editar Propietario - {collection_name}")
            edit_dialog.resize(400, 300)
            
            layout = QVBoxLayout(edit_dialog)
            
            # Formulario de edición
            form_layout = QFormLayout()
            
            owner_input = QLineEdit(owner_name)
            form_layout.addRow("Nombre del Propietario:", owner_input)
            
            email_input = QLineEdit()
            form_layout.addRow("Email:", email_input)
            
            department_input = QLineEdit()
            form_layout.addRow("Departamento:", department_input)
            
            role_input = QLineEdit()
            form_layout.addRow("Rol:", role_input)
            
            # Intentar cargar valores actuales
            try:
                if db_name in self.client.list_database_names():
                    db = self.client[db_name]
                    
                    # Buscar en metadata o colecciones relevantes
                    if 'metadata' in db.list_collection_names():
                        metadata = db.metadata.find_one({"type": "owner", "collection": collection_name})
                        if metadata:
                            email_input.setText(metadata.get('email', ''))
                            department_input.setText(metadata.get('department', ''))
                            role_input.setText(metadata.get('role', ''))
            except Exception as e:
                print(f"Error al cargar valores actuales: {e}")
                
            layout.addLayout(form_layout)
            
            # Botones de acción
            button_layout = QHBoxLayout()
            save_button = QPushButton("Guardar")
            save_button.setStyleSheet("background-color: #2ecc71; color: white;")
            button_layout.addWidget(save_button)
            
            cancel_button = QPushButton("Cancelar")
            button_layout.addWidget(cancel_button)
            
            layout.addLayout(button_layout)
            
            # Conectar botones
            save_button.clicked.connect(edit_dialog.accept)
            cancel_button.clicked.connect(edit_dialog.reject)
            
            # Mostrar diálogo
            if edit_dialog.exec() == QDialog.DialogCode.Accepted:
                # Aquí iría la lógica para guardar los cambios
                pass
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al editar información del propietario: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)

    def show_database_details(self, table):
        """Mostrar estadísticas y detalles de la base de datos seleccionada"""
        try:
            # Verificar si hay una fila seleccionada
            if not table or table.currentRow() < 0:
                QMessageBox.warning(self, "Advertencia", "Por favor, seleccione una base de datos primero")
                return
                
            # Obtener el nombre de la base de datos
            db_name = table.item(table.currentRow(), 0).text()
            
            # Obtener estadísticas de la base de datos
            db = self.client[db_name]
            stats = db.command("dbStats")
            stats = db.command("dbStats")
            
            # Crear diálogo para mostrar detalles
            detail_dialog = QDialog(self)
            detail_dialog.setWindowTitle(f"Detalles - {db_name}")
            detail_dialog.resize(500, 400)
            
            detail_layout = QVBoxLayout(detail_dialog)
            
            # Mostrar estadísticas
            stats_text = f"""
            <h3>Estadísticas de la Base de Datos: {db_name}</h3>
            <p><b>Colecciones:</b> {stats.get('collections', 0)}</p>
            <p><b>Vistas:</b> {stats.get('views', 0)}</p>
            <p><b>Objetos:</b> {stats.get('objects', 0)}</p>
            <p><b>Tamaño de Datos:</b> {stats.get('dataSize', 0) / (1024*1024):.2f} MB</p>
            <p><b>Tamaño de Almacenamiento:</b> {stats.get('storageSize', 0) / (1024*1024):.2f} MB</p>
            <p><b>Índices:</b> {stats.get('indexes', 0)}</p>
            <p><b>Tamaño de Índices:</b> {stats.get('indexSize', 0) / (1024*1024):.2f} MB</p>
            """
            
            stats_label = QLabel(stats_text)
            stats_label.setTextFormat(Qt.TextFormat.RichText)
            detail_layout.addWidget(stats_label)
            
            # Listar colecciones
            collections_group = QGroupBox("Colecciones")
            collections_layout = QVBoxLayout(collections_group)
            
            collections_list = QListWidget()
            try:
                collection_names = db.list_collection_names()
                for col in collection_names:
                    count = db[col].count_documents({})
                    collections_list.addItem(f"{col} ({count} documentos)")
            except Exception as e:
                collections_list.addItem(f"Error al listar colecciones: {str(e)}")
                
            collections_layout.addWidget(collections_list)
            detail_layout.addWidget(collections_group)
            
            # Botón para cerrar
            close_button = QPushButton("Cerrar")
            close_button.clicked.connect(detail_dialog.accept)
            detail_layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
            detail_dialog.exec()
            
        except Exception as e:
            self.show_status_message(f"Error: {str(e)}", error=True)

    def edit_database_fields(self):
        """Editar campos de la base de datos"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Seleccionar colección para editar
            collections = self.db.list_collection_names()
            
            if not collections:
                QMessageBox.information(self, "Información", "No hay colecciones disponibles")
                return
                
            # Diálogo para seleccionar colección
            select_dialog = CollectionSelectDialog(
                self, collections,
                label="Seleccione una colección para editar sus campos:"
            )
            if not select_dialog.exec():
                return
                
            collection_name = select_dialog.get_selected_collection()
            if not collection_name:
                QMessageBox.warning(self, "Advertencia", "No se ha seleccionado ninguna colección")
                return
            # Obtener un documento de muestra de la colección
            sample_doc = self.db[collection_name].find_one()
            if not sample_doc:
                QMessageBox.warning(self, "Advertencia", "La colección está vacía, no hay campos para editar")
                return
                
            # Crear diálogo para editar campos
            field_dialog = QDialog(self)
            field_dialog.setWindowTitle(f"Editar Campos - {collection_name}")
            field_dialog.resize(600, 500)
            
            dialog_layout = QVBoxLayout(field_dialog)
            
            # Información de ayuda
            help_text = QLabel("Este diálogo permite gestionar los campos de la colección. "
                               "Puede marcar campos como 'Requerido' o 'Solo Lectura', "
                               "y establecer sus tipos de datos.")
            help_text.setWordWrap(True)
            dialog_layout.addWidget(help_text)
            
            # Tabla de campos
            fields_table = QTableWidget()
            fields_table.setColumnCount(4)
            fields_table.setHorizontalHeaderLabels(["Campo", "Tipo", "Requerido", "Solo Lectura"])
            
            # Obtener campos del documento
            fields = list(sample_doc.keys())
            fields_table.setRowCount(len(fields))
            
            # Llenar tabla con los campos
            for i, field in enumerate(fields):
                # Nombre del campo
                field_item = QTableWidgetItem(field)
                if field == "_id":  # Hacer _id no editable
                    field_item.setFlags(field_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                fields_table.setItem(i, 0, field_item)
                
                # Tipo de dato
                value = sample_doc[field]
                type_name = type(value).__name__
                type_combo = QComboBox()
                type_combo.addItems(["string", "number", "boolean", "array", "object", "date", "objectid"])
                if type_name == "str":
                    type_combo.setCurrentText("string")
                elif type_name in ("int", "float"):
                    type_combo.setCurrentText("number")
                elif type_name == "bool":
                    type_combo.setCurrentText("boolean")
                elif type_name == "list":
                    type_combo.setCurrentText("array")
                elif type_name == "dict":
                    type_combo.setCurrentText("object")
                elif type_name == "datetime":
                    type_combo.setCurrentText("date")
                elif type_name == "ObjectId":
                    type_combo.setCurrentText("objectid")
                fields_table.setCellWidget(i, 1, type_combo)
                
                # Casillas de verificación para Requerido y Solo Lectura
                required_check = QCheckBox()
                required_check.setChecked(field == "_id")  # _id siempre es requerido
                if field == "_id":
                    required_check.setEnabled(False)
                required_widget = QWidget()
                required_layout = QHBoxLayout(required_widget)
                required_layout.addWidget(required_check)
                required_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                required_layout.setContentsMargins(0, 0, 0, 0)
                fields_table.setCellWidget(i, 2, required_widget)
                
                readonly_check = QCheckBox()
                readonly_check.setChecked(field == "_id")  # _id siempre es de solo lectura
                if field == "_id":
                    readonly_check.setEnabled(False)
                readonly_widget = QWidget()
                readonly_layout = QHBoxLayout(readonly_widget)
                readonly_layout.addWidget(readonly_check)
                readonly_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                readonly_layout.setContentsMargins(0, 0, 0, 0)
                fields_table.setCellWidget(i, 3, readonly_widget)
            
            fields_table.resizeColumnsToContents()
            dialog_layout.addWidget(fields_table)
            
            # Botones de acción
            button_box = QDialogButtonBox()
            
            save_button = QPushButton("Guardar Cambios")
            save_button.setStyleSheet("background-color: #2ecc71; color: white;")
            button_box.addButton(save_button, QDialogButtonBox.ButtonRole.AcceptRole)
            
            add_field_button = QPushButton("Añadir Campo")
            add_field_button.setStyleSheet("background-color: #3498db; color: white;")
            button_box.addButton(add_field_button, QDialogButtonBox.ButtonRole.ActionRole)
            
            remove_field_button = QPushButton("Eliminar Campo")
            remove_field_button.setStyleSheet("background-color: #e74c3c; color: white;")
            button_box.addButton(remove_field_button, QDialogButtonBox.ButtonRole.ActionRole)
            
            cancel_button = QPushButton("Cancelar")
            button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
            
            dialog_layout.addWidget(button_box)
            
            def add_new_field():
                field_dialog = QDialog(self)
                field_dialog.setWindowTitle("Añadir Nuevo Campo")
                
                field_layout = QFormLayout(field_dialog)
                
                field_name = QLineEdit()
                field_layout.addRow("Nombre del Campo:", field_name)
                
                field_type = QComboBox()
                field_type.addItems(["string", "number", "boolean", "array", "object", "date"])
                field_layout.addRow("Tipo de Dato:", field_type)
                
                field_required = QCheckBox()
                field_layout.addRow("Campo Requerido:", field_required)
                
                field_buttons = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                )
                field_buttons.accepted.connect(field_dialog.accept)
                field_buttons.rejected.connect(field_dialog.reject)
                field_layout.addRow(field_buttons)
                
                if field_dialog.exec():
                    new_name = field_name.text().strip()
                    if not new_name:
                        QMessageBox.warning(field_dialog, "Advertencia", "El nombre del campo no puede estar vacío")
                        return
                        
                    # Verificar si el campo ya existe
                    for row in range(fields_table.rowCount()):
                        if fields_table.item(row, 0).text() == new_name:
                            QMessageBox.warning(field_dialog, "Advertencia", f"El campo '{new_name}' ya existe")
                            return
                    
                    # Añadir nuevo campo a la tabla
                    row = fields_table.rowCount()
                    fields_table.setRowCount(row + 1)
                    
                    # Nombre del campo
                    fields_table.setItem(row, 0, QTableWidgetItem(new_name))
                    
                    # Tipo de dato
                    type_combo = QComboBox()
                    type_combo.addItems(["string", "number", "boolean", "array", "object", "date", "objectid"])
                    type_combo.setCurrentText(field_type.currentText())
                    fields_table.setCellWidget(row, 1, type_combo)
                    
                    # Checkbox para requerido
                    required_check = QCheckBox()
                    required_check.setChecked(field_required.isChecked())
                    required_widget = QWidget()
                    required_layout = QHBoxLayout(required_widget)
                    required_layout.addWidget(required_check)
                    required_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    required_layout.setContentsMargins(0, 0, 0, 0)
                    fields_table.setCellWidget(row, 2, required_widget)
                    
                    # Checkbox para solo lectura
                    readonly_check = QCheckBox()
                    readonly_widget = QWidget()
                    readonly_layout = QHBoxLayout(readonly_widget)
                    readonly_layout.addWidget(readonly_check)
                    readonly_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    readonly_layout.setContentsMargins(0, 0, 0, 0)
                    fields_table.setCellWidget(row, 3, readonly_widget)
            
            # Funcionalidad para eliminar un campo seleccionado
            def remove_selected_field():
                selected_row = fields_table.currentRow()
                if selected_row < 0:
                    QMessageBox.warning(field_dialog, "Advertencia", "Por favor seleccione un campo para eliminar")
                    return
                    
                field_name = fields_table.item(selected_row, 0).text()
                
                # No permitir eliminar el campo _id
                if field_name == "_id":
                    QMessageBox.warning(field_dialog, "Advertencia", "No se puede eliminar el campo _id")
                    return
                    
                confirm = QMessageBox.question(
                    field_dialog,
                    "Confirmar Eliminación",
                    f"¿Está seguro de que desea eliminar el campo '{field_name}'?\nEsta acción afectará a la estructura de la colección.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if confirm == QMessageBox.StandardButton.Yes:
                    fields_table.removeRow(selected_row)
            
            # Conectar botones a sus funciones
            add_field_button.clicked.connect(add_new_field)
            remove_field_button.clicked.connect(remove_selected_field)
            cancel_button.clicked.connect(field_dialog.reject)
            
            # Función para guardar los cambios
            def save_field_changes():
                try:
                    # Crear diccionario de esquema para la validación
                    schema = {"bsonType": "object", "required": [], "properties": {}}
                    
                    # Procesar cada campo
                    fields_to_update = {}
                    for row in range(fields_table.rowCount()):
                        field_name = fields_table.item(row, 0).text()
                        field_type = fields_table.cellWidget(row, 1).currentText()
                        required_widget = fields_table.cellWidget(row, 2).findChild(QCheckBox)
                        readonly_widget = fields_table.cellWidget(row, 3).findChild(QCheckBox)
                        
                        # Agregar a la lista de campos requeridos si está marcado
                        if required_widget.isChecked():
                            schema["required"].append(field_name)
                        
                        # Definir propiedades del campo
                        field_props = {"bsonType": field_type}
                        if readonly_widget.isChecked():
                            field_props["readonly"] = True
                            
                        schema["properties"][field_name] = field_props
                        
                        # Preparar actualización para campos nuevos o modificados
                        if field_name not in sample_doc:
                            # Establecer un valor predeterminado según el tipo
                            if field_type == "string":
                                fields_to_update[field_name] = ""
                            elif field_type == "number":
                                fields_to_update[field_name] = 0
                            elif field_type == "boolean":
                                fields_to_update[field_name] = False
                            elif field_type == "array":
                                fields_to_update[field_name] = []
                            elif field_type == "object":
                                fields_to_update[field_name] = {}
                            elif field_type == "date":
                                from datetime import datetime
                                fields_to_update[field_name] = datetime.now()
                    
                    # Aplicar validación a la colección
                    try:
                        self.db.command("collMod", collection_name, {
                            "validator": {"$jsonSchema": schema},
                            "validationLevel": "moderate"
                        })
                        
                        # Actualizar documentos con nuevos campos predeterminados
                        if fields_to_update:
                            self.db[collection_name].update_many(
                                {},
                                {"$set": fields_to_update}
                            )
                        
                        QMessageBox.information(
                            field_dialog,
                            "Éxito",
                            f"La estructura de campos de '{collection_name}' ha sido actualizada correctamente."
                        )
                        field_dialog.accept()
                        
                        # Actualizar la vista
                        self.show_collections()
                        
                    except Exception as e:
                        QMessageBox.critical(
                            field_dialog,
                            "Error", 
                            f"Error al aplicar la validación del esquema: {str(e)}"
                        )
                        return
                    
                except Exception as e:
                    QMessageBox.critical(
                        field_dialog,
                        "Error",
                        f"Error al procesar los campos: {str(e)}"
                    )
            
            # Conectar el botón guardar a la función
            save_button.clicked.connect(save_field_changes)
            
            # Ejecutar el diálogo
            field_dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al editar campos de la base de datos: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    def manage_indexes(self):
        """Crear y gestionar índices para colecciones en la base de datos"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Seleccionar colección para gestionar índices
            collections = self.db.list_collection_names()
            
            if not collections:
                QMessageBox.information(self, "Información", "No hay colecciones disponibles")
                return
                
            # Crear diálogo para seleccionar colección
            select_dialog = CollectionSelectDialog(
                self, collections,
                label="Seleccione una colección para gestionar sus índices:"
            )
            if not select_dialog.exec():
                return
                
            collection_name = select_dialog.get_selected_collection()
            if not collection_name:
                QMessageBox.warning(self, "Advertencia", "No se ha seleccionado ninguna colección")
                return
                
            # Crear diálogo principal para gestión de índices
            index_dialog = QDialog(self)
            index_dialog.setWindowTitle(f"Gestión de Índices - {collection_name}")
            index_dialog.resize(700, 500)
            
            dialog_layout = QVBoxLayout(index_dialog)
            
            # Sección de información
            info_text = QLabel("""
            <h3>Gestión de índices</h3>
            <p>Desde esta ventana puede crear, visualizar y gestionar los índices de sus colecciones MongoDB.</p>
            <p>Los índices mejoran el rendimiento de las consultas pero ocupan espacio adicional.</p>
            """)
            info_text.setWordWrap(True)
            dialog_layout.addWidget(info_text)
            
            # Crear widget con pestañas para las diferentes funciones
            tab_widget = QTabWidget()
            
            # Pestaña 1: Ver índices existentes
            existing_tab = QWidget()
            existing_layout = QVBoxLayout(existing_tab)
            
            # Tabla para mostrar índices existentes
            index_table = QTableWidget()
            index_table.setColumnCount(5)
            # Cargar los índices existentes
            try:
                collection = self.db[collection_name]
                indexes = list(collection.list_indexes())
                
                # Establecer número de filas
                index_table.setRowCount(len(indexes))
                
                # Llenar la tabla con la información de los índices
                for i, index in enumerate(indexes):
                    # Nombre del índice
                    index_table.setItem(i, 0, QTableWidgetItem(index.get('name', 'N/A')))
                    
                    # Campos del índice
                    key_fields = ', '.join([f"{k}:{v}" for k, v in index.get('key', {}).items()])
                    index_table.setItem(i, 1, QTableWidgetItem(key_fields))
                    
                    # Tipo de índice
                    index_type = "Regular"
                    if 'text' in index.get('key', {}):
                        index_type = "Texto"
                    elif '2dsphere' in index.get('key', {}):
                        index_type = "Geoespacial"
                    elif hasattr(index, 'expireAfterSeconds'):
                        index_type = "TTL"
                    index_table.setItem(i, 2, QTableWidgetItem(index_type))
                    
                    # Tamaño estimado del índice (obtenido de las estadísticas)
                    try:
                        stats = self.db.command({"collStats": collection_name})
                        index_sizes = stats.get('indexSizes', {})
                        size = index_sizes.get(index.get('name', ''), 0) / 1024  # KB
                        index_table.setItem(i, 3, QTableWidgetItem(f"{size:.2f} KB"))
                    except Exception:
                        index_table.setItem(i, 3, QTableWidgetItem("No disponible"))
                    
                    # Es único
                    is_unique = "Sí" if index.get('unique', False) else "No"
                    index_table.setItem(i, 4, QTableWidgetItem(is_unique))
                    
                index_table.resizeColumnsToContents()
                existing_layout.addWidget(index_table)
            except Exception as e:
                print(f"Error al configurar pestaña de índices existentes: {e}")
                QMessageBox.warning(self, "Error", f"Error al mostrar índices existentes: {str(e)}")
            
            # Pestaña 2: Crear Índice
            create_tab = QWidget()
            create_layout = QVBoxLayout(create_tab)

            form_layout = QFormLayout()
            collection_name_label = QLabel(collection_name)
            collection_name_label.setStyleSheet("font-weight: bold;")
            form_layout.addRow("Colección:", collection_name_label)

            # Selección de campos a indexar, a partir de un documento de muestra
            sample_doc = collection.find_one() or {}
            field_names = sorted(k for k in sample_doc.keys() if k != '_id')

            fields_list = QListWidget()
            fields_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            for field_name in field_names:
                fields_list.addItem(QListWidgetItem(field_name))
            form_layout.addRow("Campos a indexar:", fields_list)

            index_type_combo = QComboBox()
            index_type_combo.addItems(["Estándar", "Único", "Texto", "TTL"])
            form_layout.addRow("Tipo de índice:", index_type_combo)

            # Widget de opciones según el tipo de índice
            options_widget = QStackedWidget()

            standard_options = QWidget()
            options_widget.addWidget(standard_options)  # Estándar: sin opciones

            unique_options = QWidget()
            options_widget.addWidget(unique_options)  # Único: sin opciones

            text_options = QWidget()
            options_widget.addWidget(text_options)  # Texto: sin opciones adicionales

            ttl_widget = QWidget()
            ttl_layout = QFormLayout(ttl_widget)
            ttl_seconds = QLineEdit()
            ttl_seconds.setText("86400")  # 1 día por defecto
            ttl_layout.addRow("Segundos para expiración:", ttl_seconds)
            ttl_info = QLabel("Los documentos serán eliminados automáticamente después de este tiempo")
            ttl_info.setWordWrap(True)
            ttl_layout.addRow(ttl_info)
            options_widget.addWidget(ttl_widget)  # TTL

            index_type_combo.currentIndexChanged.connect(options_widget.setCurrentIndex)
            form_layout.addRow("Opciones:", options_widget)

            create_layout.addLayout(form_layout)

            create_buttons_layout = QHBoxLayout()
            create_button = QPushButton("Crear Índice")
            create_button.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
            create_buttons_layout.addWidget(create_button)
            cancel_button = QPushButton("Cerrar")
            create_buttons_layout.addWidget(cancel_button)
            create_layout.addLayout(create_buttons_layout)

            def refresh_indexes():
                try:
                    index_table.setRowCount(0)
                    updated_indexes = list(collection.list_indexes())
                    index_table.setRowCount(len(updated_indexes))

                    for i, index in enumerate(updated_indexes):
                        index_table.setItem(i, 0, QTableWidgetItem(index.get('name', 'N/A')))

                        key_fields = ', '.join([f"{k}:{v}" for k, v in index.get('key', {}).items()])
                        index_table.setItem(i, 1, QTableWidgetItem(key_fields))

                        index_type = "Regular"
                        if 'text' in index.get('key', {}):
                            index_type = "Texto"
                        elif '2dsphere' in index.get('key', {}):
                            index_type = "Geoespacial"
                        elif 'expireAfterSeconds' in index:
                            index_type = "TTL"
                        index_table.setItem(i, 2, QTableWidgetItem(index_type))

                        try:
                            stats = self.db.command({"collStats": collection_name})
                            index_sizes = stats.get('indexSizes', {})
                            size = index_sizes.get(index.get('name', ''), 0) / 1024
                            index_table.setItem(i, 3, QTableWidgetItem(f"{size:.2f} KB"))
                        except Exception:
                            index_table.setItem(i, 3, QTableWidgetItem("No disponible"))

                        is_unique = "Sí" if index.get('unique', False) else "No"
                        index_table.setItem(i, 4, QTableWidgetItem(is_unique))

                    index_table.resizeColumnsToContents()
                except Exception as e:
                    print(f"Error al actualizar índices: {e}")
                    QMessageBox.warning(self, "Error", f"Error al actualizar índices: {str(e)}")

            def create_index_action():
                selected_fields = [item.text() for item in fields_list.selectedItems()]
                if not selected_fields:
                    QMessageBox.warning(self, "Advertencia", "Seleccione al menos un campo para el índice")
                    return

                index_type_text = index_type_combo.currentText()
                key_dict = {}
                index_options = {}

                if index_type_text == "Estándar":
                    for field in selected_fields:
                        key_dict[field] = 1
                elif index_type_text == "Único":
                    for field in selected_fields:
                        key_dict[field] = 1
                    index_options["unique"] = True
                elif index_type_text == "Texto":
                    for field in selected_fields:
                        key_dict[field] = "text"
                elif index_type_text == "TTL":
                    if len(selected_fields) != 1:
                        QMessageBox.warning(self, "Advertencia", "Los índices TTL solo pueden tener un campo (de tipo fecha)")
                        return
                    key_dict[selected_fields[0]] = 1
                    try:
                        index_options["expireAfterSeconds"] = int(ttl_seconds.text())
                    except ValueError:
                        QMessageBox.warning(self, "Advertencia", "El tiempo de expiración debe ser un número entero de segundos")
                        return

                index_name = "_".join(selected_fields)
                if index_type_text != "Estándar":
                    index_name += f"_{index_type_text.lower()}"
                index_options["name"] = index_name

                confirm = QMessageBox.question(
                    self,
                    "Confirmar Creación",
                    f"¿Está seguro de que desea crear el índice '{index_name}'?\n\n"
                    f"Campos: {', '.join(selected_fields)}\n"
                    f"Tipo: {index_type_text}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return

                try:
                    collection.create_index(list(key_dict.items()), **index_options)
                    refresh_indexes()
                    tab_widget.setCurrentIndex(0)
                    QMessageBox.information(self, "Éxito", f"Índice '{index_name}' creado correctamente")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error al crear índice: {str(e)}")

            create_button.clicked.connect(create_index_action)
            cancel_button.clicked.connect(lambda: index_dialog.reject())

            # Pestaña 3: Rendimiento (reindexación)
            reindex_tab = QWidget()
            reindex_layout = QVBoxLayout(reindex_tab)

            reindex_info = QLabel(
                "La reindexación reconstruye todos los índices de la colección. "
                "Este proceso puede tardar y bloquea las operaciones de escritura."
            )
            reindex_info.setWordWrap(True)
            reindex_layout.addWidget(reindex_info)

            reindex_button = QPushButton("Reindexar Colección")
            reindex_button.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold;")
            reindex_layout.addWidget(reindex_button)
            reindex_layout.addStretch()

            def reindex_collection_action():
                try:
                    confirm = QMessageBox.question(
                        self,
                        "Confirmar Reindexación",
                        f"¿Está seguro de que desea reindexar la colección '{collection_name}'?\n\n"
                        "Este proceso puede tardar mucho tiempo en colecciones grandes y bloquea las operaciones de escritura.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )

                    if confirm == QMessageBox.StandardButton.Yes:
                        progress = QProgressDialog("Reindexando colección...", "Cancelar", 0, 100, self)
                        progress.setWindowModality(Qt.WindowModality.WindowModal)
                        progress.setValue(0)
                        progress.show()

                        def do_reindex():
                            try:
                                result = self.db.command("reIndex", collection_name)
                                return True, result
                            except Exception as e:
                                return False, str(e)

                        progress.setValue(30)
                        success, result = do_reindex()
                        progress.setValue(100)

                        if success:
                            QMessageBox.information(self, "Éxito", f"Colección '{collection_name}' reindexada correctamente")
                            refresh_indexes()
                        else:
                            QMessageBox.critical(self, "Error", f"Error durante la reindexación: {result}")

                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error al reindexar colección: {str(e)}")

            reindex_button.clicked.connect(reindex_collection_action)

            tab_widget.addTab(existing_tab, "Índices Existentes")
            tab_widget.addTab(create_tab, "Crear Índice")
            tab_widget.addTab(reindex_tab, "Rendimiento")
            dialog_layout.addWidget(tab_widget)

            index_dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al gestionar índices: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
                
    def verify_integrity(self):
        """Verificar la integridad de las colecciones de la base de datos"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Obtener todas las colecciones
            collections = self.db.list_collection_names()
            
            if not collections:
                QMessageBox.information(self, "Información", "No hay colecciones para verificar")
                return
                
            # Crear diálogo de progreso
            from PyQt6.QtWidgets import QProgressDialog
            from PyQt6.QtCore import Qt
            
            progress = QProgressDialog("Verificando integridad de la base de datos...", "Cancelar", 0, len(collections), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            
            # Resultados
            results = []
            
            # Verificar cada colección
            for i, collection_name in enumerate(collections):
                progress.setValue(i)
                if progress.wasCanceled():
                    break
                    
                # Ejecutar comando validate
                validate_result = self.db.command("validate", collection_name)
                is_valid = validate_result.get("valid", False)
                results.append((collection_name, is_valid))
                
            # Completar barra de progreso
            progress.setValue(len(collections))
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Resultados de Integridad de Base de Datos")
            layout = QVBoxLayout(dialog)
            
            # Tabla para resultados
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Colección", "Estado"])
            table.setRowCount(len(results))
            
            for i, (collection, valid) in enumerate(results):
                table.setItem(i, 0, QTableWidgetItem(collection))
                status_text = "Válida" if valid else "Inválida"
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(QColor("green" if valid else "red"))
                table.setItem(i, 1, status_item)
                
            table.resizeColumnsToContents()
            layout.addWidget(table)
            
            # Resumen
            valid_count = sum(1 for _, valid in results if valid)
            summary = QLabel(f"Resumen: {valid_count}/{len(results)} colecciones son válidas")
            summary.setStyleSheet("font-weight: bold; margin-top: 10px;")
            layout.addWidget(summary)
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al verificar integridad de la base de datos: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    
    def show_tutorial(self):
        """Mostrar un tutorial sobre cómo usar la aplicación"""
        try:
            # Crear un diálogo para el tutorial
            dialog = QDialog(self)
            dialog.setWindowTitle("Tutorial - Gestor de Base de Datos MongoDB")
            dialog.resize(800, 600)
            layout = QVBoxLayout(dialog)

            # Título
            title = QLabel("Guía de Uso - Gestor de Base de Datos MongoDB")
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
            layout.addWidget(title)
            
            # Crear un widget de pestañas para organizar el tutorial
            tab_widget = QTabWidget()
            intro_widget = QWidget()
            intro_layout = QVBoxLayout(intro_widget)
            
            intro_text = QLabel("""
<h3>Bienvenido al Gestor de Base de Datos MongoDB</h3>

<p>Esta aplicación le permite gestionar sus bases de datos MongoDB de forma sencilla e intuitiva.</p>

<p><b>Características principales:</b></p>
<ul>
  <li>Conectar a servidores MongoDB locales o remotos</li>
  <li>Gestionar bases de datos y colecciones</li>
  <li>Importar y exportar datos en diferentes formatos</li>
  <li>Ejecutar consultas MongoDB</li>
  <li>Gestionar usuarios y permisos</li>
  <li>Verificar la integridad de las bases de datos</li>
</ul>

<p>En las siguientes secciones encontrará información detallada sobre cómo utilizar cada función.</p>
""")
            intro_text.setWordWrap(True)
            intro_text.setTextFormat(Qt.TextFormat.RichText)
            intro_layout.addWidget(intro_text)
            
            # Pestaña de Conexión
            connect_widget = QWidget()
            connect_layout = QVBoxLayout(connect_widget)
            
            connect_text = QLabel("""
<h3>Conectarse a MongoDB</h3>

<p><b>Para conectarse a una base de datos:</b></p>
<ol>
  <li>Utilice el menú <b>Conexión > Conectar</b> o haga clic en el botón <b>Conectar a MongoDB</b> en el panel principal.</li>
  <li>Introduzca su cadena de conexión MongoDB en el formato: <code>mongodb://usuario:contraseña@host:puerto/</code></li>
  <li>Especifique el nombre de la base de datos a la que desea conectarse.</li>
  <li>Haga clic en <b>Aceptar</b> para establecer la conexión.</li>
</ol>

<p><b>Para cambiar de base de datos:</b></p>
<ol>
  <li>Utilice el menú <b>Base de Datos > Cambiar Base de Datos</b>.</li>
  <li>Seleccione la base de datos deseada de la lista.</li>
</ol>

<p><b>Para desconectar:</b></p>
<ol>
  <li>Utilice el menú <b>Conexión > Desconectar</b>.</li>
</ol>
""")
            connect_text.setWordWrap(True)
            connect_text.setTextFormat(Qt.TextFormat.RichText)
            connect_layout.addWidget(connect_text)
            
            # Pestaña de Colecciones
            collections_widget = QWidget()
            collections_layout = QVBoxLayout(collections_widget)
            
            collections_text = QLabel("""
<h3>Gestión de Colecciones</h3>

<p><b>Para ver colecciones:</b></p>
<ol>
  <li>Una vez conectado, la pestaña <b>Colecciones</b> muestra todas las colecciones disponibles.</li>
  <li>Haga doble clic en una colección para ver sus documentos.</li>
</ol>

<p><b>Para crear una nueva colección:</b></p>
<ol>
  <li>Utilice el menú <b>Colecciones > Crear Colección</b>.</li>
  <li>Introduzca el nombre de la nueva colección.</li>
  <li>Haga clic en <b>Aceptar</b> para crearla.</li>
</ol>

<p><b>Para eliminar una colección:</b></p>
<ol>
  <li>Utilice el menú <b>Colecciones > Eliminar Colección</b>.</li>
  <li>Seleccione la colección que desea eliminar.</li>
  <li>Confirme la eliminación cuando se solicite.</li>
</ol>
""")
            collections_text.setWordWrap(True)
            collections_text.setTextFormat(Qt.TextFormat.RichText)
            collections_layout.addWidget(collections_text)
            
            # Pestaña de Consultas
            queries_widget = QWidget()
            queries_layout = QVBoxLayout(queries_widget)
            
            queries_text = QLabel("""
<h3>Consultas MongoDB</h3>

<p>En la pestaña <b>Consultas</b> puede ejecutar comandos MongoDB utilizando la sintaxis:</p>
<code>db.collection.operation(parameters)</code>

<p><b>Ejemplos de consultas:</b></p>
<ul>
  <li><code>db.users.find({})</code> - Buscar todos los documentos en la colección "users"</li>
  <li><code>db.users.find({"nombre": "Juan"})</code> - Buscar documentos donde el campo "nombre" sea "Juan"</li>
  <li><code>db.users.insertOne({"nombre": "Ana", "email": "ana@ejemplo.com"})</code> - Insertar un nuevo documento</li>
  <li><code>db.users.updateOne({"nombre": "Juan"}, {"$set": {"email": "juan@ejemplo.com"}})</code> - Actualizar un documento</li>
  <li><code>db.users.deleteOne({"nombre": "Juan"})</code> - Eliminar un documento</li>
  <li><code>db.users.countDocuments({"activo": true})</code> - Contar documentos según un criterio</li>
</ul>

<p><b>Operadores comunes:</b></p>
<ul>
  <li><code>$eq</code> - Igual a (=)</li>
  <li><code>$ne</code> - No igual a (!=)</li>
  <li><code>$gt</code> - Mayor que (>)</li>
  <li><code>$lt</code> - Menor que (<)</li>
  <li><code>$in</code> - En un array de valores</li>
  <li><code>$and</code> - Operador lógico AND</li>
  <li><code>$or</code> - Operador lógico OR</li>
</ul>

<p>Para ejecutar una consulta, escriba el comando en el editor y pulse el botón <b>Ejecutar</b>.</p>
""")
            queries_text.setWordWrap(True)
            queries_text.setTextFormat(Qt.TextFormat.RichText)
            queries_layout.addWidget(queries_text)
            
            # Pestaña de Importación/Exportación
            import_export_widget = QWidget()
            import_export_layout = QVBoxLayout(import_export_widget)
            
            import_export_text = QLabel("""
<h3>Importación y Exportación de Datos</h3>

<p><b>Para importar datos:</b></p>
<ol>
  <li>Utilice el menú <b>Datos > Importar Datos</b>.</li>
  <li>Seleccione el formato de origen (JSON, CSV, BSON).</li>
  <li>Elija el archivo a importar.</li>
  <li>Seleccione la colección de destino.</li>
  <li>Configure las opciones adicionales de importación.</li>
  <li>Haga clic en <b>Importar</b> para iniciar el proceso.</li>
</ol>

<p><b>Para exportar datos:</b></p>
<ol>
  <li>Utilice el menú <b>Datos > Exportar Datos</b>.</li>
  <li>Seleccione la colección a exportar.</li>
  <li>Elija el formato de exportación (JSON, CSV, BSON).</li>
  <li>Especifique la ubicación del archivo de salida.</li>
  <li>Configure las opciones adicionales de exportación.</li>
  <li>Haga clic en <b>Exportar</b> para iniciar el proceso.</li>
</ol>

<p><b>Formatos soportados:</b></p>
<ul>
  <li><b>JSON</b> - Formato estándar para intercambio de datos</li>
  <li><b>CSV</b> - Formato de valores separados por comas</li>
  <li><b>BSON</b> - Formato binario de MongoDB</li>
</ul>
""")
            import_export_text.setWordWrap(True)
            import_export_text.setTextFormat(Qt.TextFormat.RichText)
            import_export_layout.addWidget(import_export_text)

            # Pestaña de Usuarios
            users_widget = QWidget()
            users_layout = QVBoxLayout(users_widget)

            users_text = QLabel("""
<h3>Gestión de Usuarios</h3>

<p><b>Para ver usuarios existentes:</b></p>
<ol>
  <li>Utilice el menú <b>Administración > Listar Usuarios</b>.</li>
  <li>Se mostrará una tabla con todos los usuarios en la base de datos.</li>
</ol>

<p><b>Para crear un nuevo usuario:</b></p>
<ol>
  <li>Utilice el menú <b>Administración > Crear Usuario</b>.</li>
  <li>Complete la información del usuario (nombre, email, contraseña).</li>
  <li>Seleccione el rol del usuario (admin, readWrite, readOnly).</li>
  <li>Haga clic en <b>Crear Usuario</b> para guardarlo.</li>
</ol>

<p><b>Para buscar usuarios:</b></p>
<ol>
  <li>Utilice el menú <b>Administración > Buscar Usuario</b>.</li>
  <li>Seleccione el tipo de búsqueda (Por ID, Por Nombre, Por Email).</li>
  <li>Introduzca el texto de búsqueda.</li>
  <li>Haga clic en <b>Buscar</b> para encontrar usuarios que coincidan.</li>
</ol>

<p><b>Para modificar un usuario:</b></p>
<ol>
  <li>Primero localice el usuario mediante la lista o búsqueda.</li>
  <li>Seleccione el usuario y haga clic en <b>Editar Seleccionado</b>.</li>
  <li>Modifique los campos necesarios.</li>
  <li>Haga clic en <b>Guardar Cambios</b> para actualizar la información.</li>
</ol>
""")
            users_text.setWordWrap(True)
            users_text.setTextFormat(Qt.TextFormat.RichText)
            users_layout.addWidget(users_text)
            
            # Pestaña de Verificación de Integridad
            integrity_widget = QWidget()
            integrity_layout = QVBoxLayout(integrity_widget)
            
            integrity_text = QLabel("""
<h3>Verificación de Integridad</h3>

<p><b>Para verificar la integridad de la base de datos:</b></p>
<ol>
  <li>Utilice el menú <b>Herramientas > Verificar Integridad</b>.</li>
  <li>La aplicación verificará la validez de todas las colecciones.</li>
  <li>Se mostrará un informe con los resultados de la verificación.</li>
</ol>

<p><b>Para editar los campos de una colección:</b></p>
<ol>
  <li>Utilice el menú <b>Herramientas > Editar Estructura de Campos</b>.</li>
  <li>Seleccione la colección que desea modificar.</li>
  <li>Modifique, añada o elimine campos según sea necesario.</li>
  <li>Especifique si los campos son requeridos o de solo lectura.</li>
  <li>Haga clic en <b>Guardar Cambios</b> para aplicar las modificaciones.</li>
</ol>

<p><b>Para gestionar índices:</b></p>
<ol>
  <li>Utilice el menú <b>Herramientas > Gestionar Índices</b>.</li>
  <li>Seleccione la colección para gestionar sus índices.</li>
  <li>Cree, modifique o elimine índices según sea necesario.</li>
</ol>

<p>La verificación regular de la integridad ayuda a mantener la salud de su base de datos y prevenir problemas de datos.</p>
""")
            integrity_text.setWordWrap(True)
            integrity_text.setTextFormat(Qt.TextFormat.RichText)
            integrity_layout.addWidget(integrity_text)
            
            # Añadir las pestañas al widget de pestañas
            tab_widget.addTab(intro_widget, "Introducción")
            tab_widget.addTab(connect_widget, "Conexión")
            tab_widget.addTab(collections_widget, "Colecciones")
            tab_widget.addTab(queries_widget, "Consultas")
            tab_widget.addTab(import_export_widget, "Importación/Exportación")
            tab_widget.addTab(users_widget, "Usuarios")
            tab_widget.addTab(integrity_widget, "Integridad")
            
            # Añadir el widget de pestañas al layout principal
            layout.addWidget(tab_widget)
            
            # Botones de navegación
            nav_layout = QHBoxLayout()
            
            prev_button = QPushButton("Anterior")
            prev_button.setIcon(QIcon.fromTheme("go-previous"))
            prev_button.clicked.connect(lambda: tab_widget.setCurrentIndex(max(0, tab_widget.currentIndex() - 1)))
            
            next_button = QPushButton("Siguiente")
            next_button.setIcon(QIcon.fromTheme("go-next"))
            next_button.clicked.connect(lambda: tab_widget.setCurrentIndex(min(tab_widget.count() - 1, tab_widget.currentIndex() + 1)))
            
            close_button = QPushButton("Cerrar")
            close_button.clicked.connect(dialog.accept)
            
            nav_layout.addWidget(prev_button)
            nav_layout.addWidget(next_button)
            nav_layout.addStretch()
            nav_layout.addWidget(close_button)
            
            layout.addLayout(nav_layout)
            
            # Mostrar el diálogo
            dialog.exec()

        except Exception:
            try:
                # Don't set parent to None as it can cause issues
                if hasattr(self, 'collections_tree') and self.collections_tree:
                    self.collections_tree.deleteLater()
            except:
                pass  # Silently handle deletion errors
            
            # Just recreate the tree view if its parent still exists
            if hasattr(self, 'tree_widget') and self.tree_widget and not sip.isdeleted(self.tree_widget):
                # Remove old tree view if it exists
                if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
                    try:
                        self.collections_tree.setParent(None)
                        self.collections_tree.deleteLater()
                    except:
                        pass  # Silently handle deletion errors
                
                # Create new tree view
                tree_layout = self.tree_widget.layout()
                
                self.collections_tree = QTreeView(self.tree_widget)
                self.collections_tree.setHeaderHidden(True)
                self.collections_tree.setMinimumWidth(250)
                self.collections_tree.setObjectName("collectionsTreeView")
                
                # Find the right position to insert the tree view
                for i in range(tree_layout.count()):
                    item = tree_layout.itemAt(i)
                    if item.widget() and isinstance(item.widget(), QLabel):
                        tree_layout.insertWidget(i+1, self.collections_tree)
                        break
                    elif i == tree_layout.count() - 1:
                        # If no label found, add to the beginning
                        tree_layout.insertWidget(0, self.collections_tree)
            
    def closeEvent(self, event):
        """Handle window close event"""
        try:
            # Cleanup operations
            print("\n--- Closing main window ---")
            
            # Clear model item references first to prevent dangling references
            if hasattr(self, '_model_items'):
                self._model_items.clear()
            if hasattr(self, '_db_items'):
                self._db_items.clear()
                
            # Explicitly disconnect signals to prevent crashes
            try:
                if hasattr(self, 'connection_status_changed'):
                    self.connection_status_changed.disconnect()
                    
                if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
                    try:
                        self.collections_tree.doubleClicked.disconnect()
                    except:
                        pass
            except Exception as e:
                print(f"Error disconnecting signals: {e}")
            
            # Set model to None before deleting tree view
            if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
                try:
                    self.collections_tree.setModel(None)
                except:
                    pass
                    
            # Clear model
            if hasattr(self, 'collections_model') and self.collections_model:
                try:
                    self.collections_model.clear()
                    self.collections_model = None
                except:
                    pass
                
            # Clean up resources
            if hasattr(self, 'limpiar_recursos'):
                self.limpiar_recursos()
                
            # Delete tree view last
            try:
                # Don't set parent to None as it can cause issues
                if hasattr(self, 'collections_tree') and self.collections_tree:
                    self.collections_tree.deleteLater()
            except:
                pass  # Silently handle deletion errors
            event.accept()
        except Exception as e:
            print(f"Error during close event: {e}")
            traceback.print_exc()
            event.accept()  # Accept the event even if there's an error
            
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
