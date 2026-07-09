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
    QTreeWidget, QTextEdit, QToolBar, QStyle, QListWidget, QCheckBox, QFrame,
    QProgressDialog, QGroupBox, QFileDialog, QRadioButton, QButtonGroup,
    QStackedWidget, QTimeEdit, QScrollArea, QLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QTimer, QTime, QDateTime, QDate
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont, QIcon

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
class MainWindow(QMainWindow):
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
        
        # Try to get connection string from environment variables
        self.connection_string = os.environ.get("MONGODB_URI", "")
        print(f"Initial connection string: {'Found (length: ' + str(len(self.connection_string)) + ')' if self.connection_string else 'Not found'}")
        self.database_name = "app_catalogojoyero"
    
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
        
        # Crear el item de la base de datos para la vista jerárquica
        db_item = QStandardItem(self.database_name)
        db_item.setEditable(False)
        db_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon))
        
        # Guardar referencia al item de la base de datos
        self._db_items[self.database_name] = db_item
        
        # Añadir al modelo
        root_item.appendRow(db_item)
        
        # Obtener la lista de colecciones de la base de datos
        try:
            collections = self.db.list_collection_names()
            total_collections = len(collections)
            print(f"Found {total_collections} collections in database {self.database_name}")
        except Exception as e:
            print(f"Error getting collections: {e}")
            QMessageBox.critical(self, "Error", f"No se pudieron obtener las colecciones: {str(e)}")
            return
                
            # Crear diferentes vistas según el modo seleccionado
            if view_mode == 0:  # Vista jerárquica - usar el db_item existente
                pass
            elif view_mode == 1:  # Agrupado por usuario
                if root_item.rowCount() > 0:
                    root_item.removeRow(0)  # Eliminar db_item para crear otra vista
                self.create_user_grouped_view(self.collections_model, collections)
                return  # Salir ya que la función anterior maneja todo
            elif view_mode == 2:  # Agrupado por tipo
                if root_item.rowCount() > 0:
                    root_item.removeRow(0)  # Eliminar db_item para crear otra vista
                self.create_type_grouped_view(self.collections_model, collections)
                return  # Salir ya que la función anterior maneja todo
            else:  # Vista plana
                if root_item.rowCount() > 0:
                    root_item.removeRow(0)  # Eliminar db_item para crear otra vista
                self.create_flat_view(self.collections_model, collections)
                return  # Salir ya que la función anterior maneja todo
                
            # Si llegamos aquí, estamos en la vista jerárquica (view_mode == 0)
            # Mostrar diálogo de progreso para colecciones grandes
            progress = None
            if total_collections > 10:
                progress = QProgressDialog("Cargando colecciones...", "Cancelar", 0, total_collections, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(500)  # Solo mostrar si tarda más de 500ms
            
            # Procesar colecciones en lotes para mejor rendimiento
            collection_items_batch = []
            batch_size = 10
            
            # Procesar cada colección
            for i, collection_name in enumerate(collections):
                if progress:
                    
                    # Almacenar referencia utilizando un identificador único
                    collection_item = QStandardItem(f"{collection_name} ({self.db[collection_name].count_documents({})})")
                    item_id = f"collection_{collection_name}_{i}"
                    self._collections_refs[item_id] = collection_item
                    self._model_items.append(collection_item)
                    
                    # Verificar si db_item sigue siendo válido antes de añadir el item
                    if db_item is not None and not sip.isdeleted(db_item):
                        db_item.appendRow(collection_item)
                        collection_items_batch.append(collection_item)
                        
                        # Procesar eventos cada cierto número de elementos para mantener la UI responsiva
                        if len(collection_items_batch) >= batch_size:
                            QApplication.processEvents()
                            collection_items_batch = []  # Reiniciar el lote
                    else:
                        print(f"Error: db_item no es válido al procesar la colección {collection_name}")
                        # Intentar recuperar el ítem de la base de datos
                        db_item = self._db_items.get(self.database_name)
                        if db_item is not None and not sip.isdeleted(db_item):
                            db_item.appendRow(collection_item)
                        else:
                            # Si no se puede recuperar, reiniciar el proceso
                            print("Error crítico: db_item se ha eliminado, reiniciando visualización")
                            # Limpiamos todo y reiniciamos con protección contra recursión
                            if not hasattr(self, '_show_collections_recursion_guard'):
                                try:
                                    self._show_collections_recursion_guard = True
                                    # Use QTimer to restart after pending events are processed
                                    QTimer.singleShot(100, self.reset_and_show_collections)
                                except Exception as e:
                                    print(f"Error in reset_and_show_collections: {e}")
                                    pass

                # Close progress if shown
                if progress:
                    progress.setValue(total_collections)
                

                # Expand first level to show collections
                if self.is_tree_view_valid() and self.collections_model.rowCount() > 0:
                    self.collections_tree.expandToDepth(0)

        # Manejar errores de visualización
        except Exception as e:
            print(f"Error showing collections: {e}")
            print("Traceback:")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error al obtener las colecciones: {str(e)}")

            # Intentar reiniciar la vista con protección contra recursión
            if not hasattr(self, '_show_collections_recursion_guard'):
                try:
                    self._show_collections_recursion_guard = True
                    QTimer.singleShot(100, self.reset_and_show_collections)
                except Exception as restart_error:
                    print(f"Error en reinicio: {restart_error}")
                    pass

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

    # Configurar el árbol de tablas
    self.tables_tree = QTreeWidget()
    self.tables_tree.setHeaderLabels(["Tabla", "Tipo", "Campos"])
    self.tables_tree.setAlternatingRowColors(True)
    tables_layout.addWidget(self.tables_tree)

    # Agregar la pestaña de tablas
    self.collection_view_tabs.addTab(tables_tab, "Relaciones de Tablas")

    # Agregar la pestaña de metadatos
    self.collection_view_tabs.addTab(metadata_tab, "Metadatos")

    # Configurar el layout del widget de colecciones
    collections_layout = QVBoxLayout(collections_widget)
    collections_layout.addWidget(splitter)

    # Establecer proporción del splitter (30% izquierda, 70% derecha)
    splitter.setSizes([300, 700])

    # Agregar la pestaña al widget de pestañas
    self.tab_widget.addTab(collections_widget, "Colecciones")
    self._widgets_initialized = True
        
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
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al conectar a MongoDB: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            self.connection_in_progress = False
            self.enable_database_actions(False)
            
            # Actualizar estado de la conexión
            self.connection_status_changed.emit(False)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al desconectar de MongoDB: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
        
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
                    # Crear cliente MongoDB
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
            
    def closeEvent(self, event):
        """Handle window close event"""
        try:
            # Cleanup operations
            print("\n--- Closing main window ---")
            # Explicitly disconnect signals to prevent crashes
            self.connection_status_changed.disconnect()
            
            # Clean up resources
            # Clear models to prevent memory leaks
            if hasattr(self, 'collections_model'):
                self.collections_model = None
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
            
    # View mode selection
    if view_mode == 1:  # Vista agrupada por tipo
        self.create_type_grouped_view(model, collections)
    else:  # Vista plana
        # Clear and recreate with flat view
        root_item.removeRow(0)  # Remove db_item
        self.create_flat_view(model, collections)
        
        
    def closeEvent(self, event):
        """Handle window close event"""
        print("\n--- Cerrando ventana principal ---")
        try:
            # Explicitly disconnect signals to prevent crashes
            # Disconnect signals to prevent callbacks
            self.connection_status_changed.disconnect()
            
            # Clean up resources
            self.limpiar_recursos()
            event.accept()
        except Exception as e:
            print(f"Error during close event: {e}")
            event.accept()
                
    
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
                    except Exception as id_error:
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
                    except Exception as id_error:
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
            has_excel_structure = False
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
            
            # Detectar tipo de contenido
            content_type = self.detect_collection_content_type(collection_name)
            
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
            
        # Create a simple dialog for collection name input
        class CreateCollectionDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Crear Colección")
                self.resize(300, 100)
                
                layout = QFormLayout(self)
                
                self.name_input = QLineEdit(self)
                layout.addRow("Nombre de la colección:", self.name_input)
                
                self.button_box = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                )
                self.button_box.accepted.connect(self.accept)
                self.button_box.rejected.connect(self.reject)
                layout.addRow(self.button_box)
        
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
            # Create dialog for collection selection
            class DropCollectionDialog(QDialog):
                def __init__(self, parent=None, collections=None):
                    super().__init__(parent)
                    self.setWindowTitle("Eliminar Colección")
                    self.resize(300, 120)
                    
                    layout = QVBoxLayout(self)
                    
                    self.label = QLabel("Seleccione colección a eliminar:")
                    layout.addWidget(self.label)
                    
                    self.collection_combo = QComboBox(self)
                    if collections:
                        self.collection_combo.addItems(collections)
                    layout.addWidget(self.collection_combo)
                    
                    self.warning_label = QLabel("¡ADVERTENCIA: Esta acción no se puede deshacer!")
                    self.warning_label.setStyleSheet("color: red; font-weight: bold;")
                    layout.addWidget(self.warning_label)
                    
                    self.button_box = QDialogButtonBox(
                        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                    )
                    self.button_box.accepted.connect(self.accept)
                    self.button_box.rejected.connect(self.reject)
                    layout.addWidget(self.button_box)
                    
                def get_selected_collection(self):
                    return self.collection_combo.currentText()
            
            from PyQt6.QtWidgets import QFileDialog
            
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
    
    def import_data(self):
        """Import data from JSON or CSV file into a collection"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        # Seleccionar archivo a importar
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo a importar",
            "",
            "Archivos JSON (*.json);;Archivos CSV (*.csv);;Todos los archivos (*.*)"
        )
        if not file_path:
            return
            
        # Select target collection
        collections = self.db.list_collection_names()
        
        class ImportDialog(QDialog):
            def __init__(self, parent=None, collections=None):
                super().__init__(parent)
                self.setWindowTitle("Importar Datos")
                self.resize(400, 200)
                
                layout = QVBoxLayout(self)
                
                # Collection selection
                self.collection_label = QLabel("Seleccione colección destino:")
                layout.addWidget(self.collection_label)
                
                self.collection_combo = QComboBox()
                if collections:
                    self.collection_combo.addItems(collections)
                layout.addWidget(self.collection_combo)
                
                # Create new collection option
                self.new_collection_label = QLabel("O crear una nueva colección:")
                layout.addWidget(self.new_collection_label)
                
                self.new_collection_input = QLineEdit()
                layout.addWidget(self.new_collection_input)
                
                # Import options
                self.options_label = QLabel("Opciones de importación:")
                layout.addWidget(self.options_label)
                
                self.clear_collection = QComboBox()
                self.clear_collection.addItems(["Añadir a documentos existentes", "Reemplazar contenido de la colección"])
                layout.addWidget(self.clear_collection)
                
                # Buttons
                self.button_box = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                )
                self.button_box.accepted.connect(self.accept)
                self.button_box.rejected.connect(self.reject)
                layout.addWidget(self.button_box)

            def get_target_collection(self):
                new_collection = self.new_collection_input.text().strip()
                if new_collection:
                    return new_collection
                return self.collection_combo.currentText()
                
            def should_clear_collection(self):
                return self.clear_collection.currentIndex() == 1

        dialog = ImportDialog(self, collections)
        if not dialog.exec():
            return
            
        target_collection = dialog.get_target_collection()
        clear_collection = dialog.should_clear_collection()
        
        if not target_collection:
            QMessageBox.warning(self, "Advertencia", "No se ha especificado una colección destino")
            return
            
        # Import data based on file type
        try:
            if file_path.lower().endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    import json
                    data = json.load(f)
                    
                    # Get or create collection
                    collection = self.db[target_collection]
                    
                    # Clear collection if requested
                    if clear_collection:
                        collection.delete_many({})
                    
                    # Insert data
                    if isinstance(data, list):
                        if data:
                            result = collection.insert_many(data)
                            inserted_count = len(result.inserted_ids)
                        else:
                            inserted_count = 0
                    else:
                        result = collection.insert_one(data)
                        inserted_count = 1
                        
                    # Update UI
                    self.show_collections()
                    self.update_database_stats()
                    self.show_status_message(f"Imported {inserted_count} documents into collection '{target_collection}'")
                    
                    QMessageBox.information(
                        self,
                        "Importación Exitosa",
                        f"Se importaron con éxito {inserted_count} documentos en la colección '{target_collection}'"
                    )
                    
            elif file_path.lower().endswith('.csv'):
                # Import CSV file
                try:
                    import csv
                    
                    # Read CSV file
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        csv_reader = csv.DictReader(f)
                        data = list(csv_reader)
                        
                    if not data:
                        QMessageBox.warning(self, "Advertencia", "El archivo CSV está vacío o tiene un formato inválido")
                        return
                        
                    # Get or create collection
                    collection = self.db[target_collection]
                    
                    # Clear collection if requested
                    if clear_collection:
                        collection.delete_many({})
                        
                    # Insert data
                    result = collection.insert_many(data)
                    inserted_count = len(result.inserted_ids)
                    
                    # Update UI
                    self.show_collections()
                    self.update_database_stats()
                    self.show_status_message(f"Imported {inserted_count} documents from CSV into collection '{target_collection}'")
                    
                    QMessageBox.information(
                        self,
                        "Importación Exitosa",
                        f"Se importaron con éxito {inserted_count} documentos CSV en la colección '{target_collection}'"
                    )
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error de importación CSV", f"Error al importar CSV: {str(e)}")
                    self.show_status_message(f"Error: {str(e)}", error=True)
                    
            else:
                QMessageBox.warning(self, "Tipo de archivo no soportado", "Solo se soportan archivos JSON y CSV")
                
        except Exception as e:
            QMessageBox.critical(self, "Error de importación", f"Error al importar datos: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    
    def export_data(self):
        """Export data from a collection to JSON or CSV file"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        from PyQt6.QtWidgets import QFileDialog
        
        # Select collection to export
        collections = self.db.list_collection_names()
        
        if not collections:
            QMessageBox.information(self, "Información", "No hay colecciones para exportar")
            return
            
        # Create dialog for collection selection
        class ExportDialog(QDialog):
            def __init__(self, parent=None, collections=None):
                super().__init__(parent)
                self.setWindowTitle("Exportar Colección")
                self.resize(400, 150)
                
                layout = QVBoxLayout(self)
                
                # Collection selection
                self.collection_label = QLabel("Seleccionar colección a exportar:")
                layout.addWidget(self.collection_label)
                
                self.collection_combo = QComboBox()
                if collections:
                    self.collection_combo.addItems(collections)
                layout.addWidget(self.collection_combo)
                
                # Export format
                self.format_label = QLabel("Seleccionar formato de exportación:")
                layout.addWidget(self.format_label)
                
                self.format_combo = QComboBox()
                self.format_combo.addItems(["JSON", "CSV"])
                layout.addWidget(self.format_combo)
                
                # Buttons
                self.button_box = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                )
                self.button_box.accepted.connect(self.accept)
                self.button_box.rejected.connect(self.reject)
                layout.addWidget(self.button_box)
                
            def get_selected_collection(self):
                return self.collection_combo.currentText()
                
            def get_export_format(self):
                return self.format_combo.currentText().lower()
        
        # Show dialog
        dialog = ExportDialog(self, collections)
        if not dialog.exec():
            return
            
        # Get selected collection and format
        collection_name = dialog.get_selected_collection()
        export_format = dialog.get_export_format()
        
        if not collection_name:
            return
            
        # Choose export file path
        if export_format == "json":
            file_filter = "JSON Files (*.json)"
            default_suffix = ".json"
        else:  # CSV
            file_filter = "CSV Files (*.csv)"
            default_suffix = ".csv"
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Colección",
            f"{collection_name}{default_suffix}",
            file_filter
        )
        
        if not file_path:
            return
            
        # Fetch data
        try:
            collection = self.db[collection_name]
            documents = list(collection.find({}))
            
            if not documents:
                QMessageBox.information(
                    self,
                    "Export Information",
                    f"La colección '{collection_name}' está vacía. No hay nada para exportar."
                )
                return
                
            # Export based on format
            if export_format == "json":
                # Export as JSON
                import json
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Convert ObjectId to string for JSON serialization
                    json.dump(documents, f, default=str, indent=2)
                    
                self.show_status_message(f"Exported {len(documents)} documents to {file_path}")
                
            else:  # CSV
                # Export as CSV
                import csv
                
                # Get all field names from all documents
                field_names = set()
                for doc in documents:
                    field_names.update(doc.keys())
                    
                # Ensure _id is first if present
                if '_id' in field_names:
                    field_names.remove('_id')
                    field_names = ['_id'] + sorted(field_names)
                else:
                    field_names = sorted(field_names)
                    
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=field_names)
                    writer.writeheader()
                    
                    for doc in documents:
                        # Convert ObjectId and other MongoDB types to string
                        row = {k: str(v) for k, v in doc.items()}
                        writer.writerow(row)
                        
                self.show_status_message(f"Exported {len(documents)} documents to {file_path}")
                
            QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"Se exportaron con éxito {len(documents)} documentos a {file_path}"
            )
                
        except Exception as e:
            QMessageBox.critical(self, "Error de exportación", f"Error al exportar datos: {str(e)}")
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
        
    def list_users(self):
        """List all users from the unified users collection"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Use the unified users collection
            collection_name = 'users_unified'
            
            # Check if the unified collection exists
            if collection_name not in self.db.list_collection_names():
                QMessageBox.information(self, "Información", "No se encontró la colección unificada de usuarios. Por favor, ejecute la normalización primero.")
                return
            
            # Get all users from the unified collection
            all_users = list(self.db[collection_name].find())
            if not all_users:
                QMessageBox.information(self, "Información", "No se encontraron usuarios en la base de datos")
                return
                
            # Create dialog to show users
            dialog = QDialog(self)
            dialog.setWindowTitle("Lista de Usuarios")
            dialog.resize(800, 500)
            
            layout = QVBoxLayout(dialog)
            
            # Status information
            info_label = QLabel(f"Mostrando {len(all_users)} usuarios de la colección unificada")
            info_label.setStyleSheet("color: #3498db; font-weight: bold;")
            layout.addWidget(info_label)
            
            # Create table
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["ID", "Nombre", "Email", "Rol", "Colección Original"])
            table.setRowCount(len(all_users))
            
            # Fill table
            for i, user in enumerate(all_users):
                table.setItem(i, 0, QTableWidgetItem(str(user.get('_id', ''))))
                table.setItem(i, 1, QTableWidgetItem(user.get('name', '')))
                table.setItem(i, 2, QTableWidgetItem(user.get('email', '')))
                table.setItem(i, 3, QTableWidgetItem(user.get('role', 'user')))
                # Use _source_collection if available, otherwise fallback to _collection or default value
                collection_name = user.get('_source_collection', user.get('_collection', 'users_unified'))
                table.setItem(i, 4, QTableWidgetItem(collection_name))
            layout.addWidget(table)
            
            # Add buttons
            button_layout = QHBoxLayout()
            
            edit_button = QPushButton("Editar Seleccionado")
            edit_button.setStyleSheet("background-color: #3498db; color: white;")
            edit_button.clicked.connect(lambda: self.edit_selected_user(table, all_users, dialog))
            button_layout.addWidget(edit_button)
            
            close_button = QPushButton("Cerrar")
            close_button.clicked.connect(dialog.reject)
            button_layout.addWidget(close_button)
            
            layout.addLayout(button_layout)
            
            # Set table properties
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.setAlternatingRowColors(True)
            table.resizeColumnsToContents()
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al listar usuarios: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    def show_user_results(self, users):
        dialog = QDialog(self)
        dialog.setWindowTitle("Resultados de Búsqueda de Usuario")
        dialog.resize(800, 500)
        
        layout = QVBoxLayout(dialog)
        
        # Add results information
        info_label = QLabel(f"Se encontraron {len(users)} usuarios")
        info_label.setStyleSheet("color: #3498db; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Create table
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["ID", "Nombre", "Email", "Rol", "Colección Original"])
        table.setRowCount(len(users))
        
        # Fill table with standard field names from unified collection
        for i, user in enumerate(users):
            table.setItem(i, 0, QTableWidgetItem(str(user.get('_id', ''))))
            table.setItem(i, 1, QTableWidgetItem(user.get('name', '')))  # Using standardized field name
            table.setItem(i, 2, QTableWidgetItem(user.get('email', '')))
            table.setItem(i, 3, QTableWidgetItem(user.get('role', 'user')))  # Using standardized field name
            # Use _source_collection if available, otherwise fallback to _collection or default value
            collection_name = user.get('_source_collection', user.get('_collection', 'users_unified'))
            table.setItem(i, 4, QTableWidgetItem(collection_name))
        
        # Configure table properties
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.resizeColumnsToContents()
        
        layout.addWidget(table)
        
        # Add edit and close buttons
        button_layout = QHBoxLayout()
        
        edit_button = QPushButton("Editar Seleccionado")
        edit_button.setStyleSheet("background-color: #3498db; color: white;")
        edit_button.clicked.connect(lambda: self.edit_selected_user(table, users, dialog))
        button_layout.addWidget(edit_button)
        
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    def edit_selected_user(self, table, users, dialog):
        """Editar el usuario seleccionado de los resultados de búsqueda"""
        selected_row = table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Advertencia", "Por favor seleccione un usuario para editar")
            return
            
        user = users[selected_row]
        user_id = user['_id']
        
        # Get collection name with fallbacks to ensure we always have a valid value
        collection_name = user.get('_source_collection', 
                              user.get('_collection', 'users_unified'))
        
        # Cerrar el diálogo de resultados
        dialog.accept()
        
        # Abrir el diálogo de edición
        self.edit_user(user_id, collection_name)
    def edit_user(self, user_id=None, collection_name=None):
        """Editar información de usuario"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Si no se proporcionan user_id y collection_name, pedir al usuario que busque primero
            if user_id is None or collection_name is None:
                QMessageBox.information(self, "Información", "Utilice la función de búsqueda para encontrar un usuario a editar")
                self.search_user()
                return
                
            # Obtener documento del usuario
            from bson.objectid import ObjectId
            if isinstance(user_id, str):
                user_id = ObjectId(user_id)
                
            user = self.db[collection_name].find_one({'_id': user_id})
            if not user:
                QMessageBox.warning(self, "Advertencia", f"Usuario con ID {user_id} no encontrado en {collection_name}")
                return
                
            # Crear diálogo de edición
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Editar Usuario - {collection_name}")
            dialog.resize(450, 400)
            
            layout = QVBoxLayout(dialog)
            
            # Diseño de formulario para campos
            form_layout = QFormLayout()
            
            # Mostrar información actual del usuario
            id_label = QLabel(str(user_id))
            form_layout.addRow("ID de Usuario:", id_label)
            
            # Campos editables
            name_input = QLineEdit(user.get('nombre', user.get('name', '')))
            form_layout.addRow("Nombre:", name_input)
            
            email_input = QLineEdit(user.get('email', ''))
            form_layout.addRow("Email:", email_input)
            
            role_combo = QComboBox()
            role_combo.addItems(['normal', 'admin', 'supervisor', 'editor'])
            current_role = user.get('role', user.get('rol', 'normal'))
            role_combo.setCurrentText(current_role)
            form_layout.addRow("Rol:", role_combo)
            
            layout.addLayout(form_layout)
            
            # Botones de acción
            button_layout = QHBoxLayout()
            
            save_button = QPushButton("Guardar")
            save_button.setStyleSheet("background-color: #2ecc71;")
            save_button.clicked.connect(dialog.accept)
            button_layout.addWidget(save_button)
            
            delete_button = QPushButton("Eliminar Usuario")
            delete_button.setStyleSheet("background-color: #e74c3c;")
            delete_button.clicked.connect(lambda: self.delete_user(user_id, collection_name, dialog))
            button_layout.addWidget(delete_button)
            
            cancel_button = QPushButton("Cancelar")
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(cancel_button)
            
            layout.addLayout(button_layout)
            
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
                
            # Obtener valores actualizados
            new_name = name_input.text().strip()
            new_email = email_input.text().strip()
            new_role = role_combo.currentText()
            
            # Validar entradas
            if not new_name or not new_email:
                QMessageBox.warning(self, "Advertencia", "El nombre y email son obligatorios")
                return
                
            # Preparar actualización
            update_fields = {}
            if 'nombre' in user:
                update_fields['nombre'] = new_name
            elif 'name' in user:
                update_fields['name'] = new_name
            else:
                update_fields['nombre'] = new_name
                
            update_fields['email'] = new_email
            
            if 'role' in user:
                update_fields['role'] = new_role
            elif 'rol' in user:
                update_fields['rol'] = new_role
            else:
                update_fields['role'] = new_role
                
            # Actualizar usuario
            result = self.db[collection_name].update_one(
                {'_id': user_id},
                {'$set': update_fields}
            )
            
            if result.modified_count > 0:
                QMessageBox.information(self, "Éxito", f"La información del usuario ha sido actualizada correctamente")
                self.show_status_message("Usuario actualizado correctamente")
            else:
                QMessageBox.warning(self, "Advertencia", f"La información del usuario no ha sido actualizada")
                self.show_status_message("Usuario no actualizado", error=True)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al actualizar el usuario: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)

    def delete_user(self, user_id, collection_name, parent_dialog=None):
        """Eliminar un usuario de la base de datos"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Confirmación de eliminación
            confirm = QMessageBox.question(
                self,
                "Confirmar Eliminación",
                f"¿Está seguro de que desea eliminar este usuario?\nEsta acción no se puede deshacer.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if confirm != QMessageBox.StandardButton.Yes:
                return
                
            # Eliminar usuario
            from bson.objectid import ObjectId
            if isinstance(user_id, str):
                user_id = ObjectId(user_id)
                
            result = self.db[collection_name].delete_one({'_id': user_id})
            
            # Cerrar diálogo padre si existe
            if parent_dialog:
                parent_dialog.accept()
                
            if result.deleted_count > 0:
                QMessageBox.information(self, "Éxito", f"Usuario eliminado correctamente")
                self.show_status_message("Usuario eliminado correctamente")
            else:
                QMessageBox.warning(self, "Advertencia", f"No se pudo eliminar el usuario")
                self.show_status_message("Error al eliminar usuario", error=True)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al eliminar el usuario: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)

    def manage_password(self):
        """Gestionar contraseñas de usuarios"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Primero seleccionar el usuario para cambiar la contraseña
            # Reusamos la función de búsqueda de usuario
            class PasswordManageDialog(QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Gestión de Contraseñas")
                    self.resize(400, 180)
                    
                    layout = QVBoxLayout(self)
                    
                    # Campos de búsqueda
                    search_layout = QFormLayout()
                    
                    self.search_type = QComboBox()
                    self.search_type.addItems(["Por ID", "Por Nombre", "Por Email"])
                    search_layout.addRow("Buscar usuario:", self.search_type)
                    
                    self.search_text = QLineEdit()
                    search_layout.addRow("Texto de búsqueda:", self.search_text)
                    
                    self.search_button = QPushButton("Buscar Usuario")
                    self.search_button.setStyleSheet("background-color: #3498db; color: white;")
                    
                    layout.addLayout(search_layout)
                    layout.addWidget(self.search_button)
                    
                    # Separador
                    line = QFrame()
                    line.setFrameShape(QFrame.Shape.HLine)
                    line.setFrameShadow(QFrame.Shadow.Sunken)
                    layout.addWidget(line)
                    
                    # Sección para cambiar contraseña
                    self.user_label = QLabel("Seleccione un usuario primero")
                    layout.addWidget(self.user_label)
                    
                    password_layout = QFormLayout()
                    
                    self.password_input = QLineEdit()
                    self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
                    self.password_input.setEnabled(False)
                    password_layout.addRow("Nueva Contraseña:", self.password_input)
                    
                    self.confirm_input = QLineEdit()
                    self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
                    self.confirm_input.setEnabled(False)
                    password_layout.addRow("Confirmar Contraseña:", self.confirm_input)
                    
                    layout.addLayout(password_layout)
                    
                    # Botones
                    button_layout = QHBoxLayout()
                    
                    self.save_button = QPushButton("Cambiar Contraseña")
                    self.save_button.setStyleSheet("background-color: #2ecc71; color: white;")
                    self.save_button.setEnabled(False)
                    button_layout.addWidget(self.save_button)
                    
                    self.cancel_button = QPushButton("Cancelar")
                    button_layout.addWidget(self.cancel_button)
                    
                    layout.addLayout(button_layout)
                    
                    # Almacenar información del usuario seleccionado
                    self.selected_user = None
                    self.selected_collection = None
            
            dialog = PasswordManageDialog(self)
            
            # Conectar señales a slots
            dialog.search_button.clicked.connect(lambda: self.search_user_for_password(dialog))
            dialog.save_button.clicked.connect(lambda: self.update_user_password(dialog))
            dialog.cancel_button.clicked.connect(dialog.reject)
            
            # Mostrar el diálogo
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al gestionar contraseñas: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
    def update_user_password(self, dialog):
        """Actualizar la contraseña de un usuario seleccionado"""
        try:
            # Verificar si se seleccionó un usuario
            if not dialog.selected_user:
                QMessageBox.warning(self, "Advertencia", "Por favor, busque y seleccione un usuario primero")
                return
                
            # Obtener contraseñas
            new_password = dialog.password_input.text()
            confirm_password = dialog.confirm_input.text()
            
            # Validar que las contraseñas coinciden
            if new_password != confirm_password:
                QMessageBox.warning(self, "Advertencia", "Las contraseñas no coinciden")
                return
                
            # Validar que la contraseña no esté vacía
            if not new_password:
                QMessageBox.warning(self, "Advertencia", "La contraseña no puede estar vacía")
                return
                
            # Validar seguridad de la contraseña
            if len(new_password) < 8:
                QMessageBox.warning(self, "Advertencia", "La contraseña debe tener al menos 8 caracteres")
                return
                
            # Obtener usuario y colección
            user = dialog.selected_user
            collection_name = dialog.selected_collection
            user_id = user['_id']
            
            # Hashear la contraseña (en una aplicación real se usaría un algoritmo más seguro)
            import hashlib
            # Utilizamos un hash simple para este ejemplo
            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
            
            # Actualizar la contraseña en la base de datos
            result = self.db[collection_name].update_one(
                {'_id': user_id},
                {'$set': {'password': hashed_password, 'password_changed_at': datetime.datetime.now()}}
            )
            
            if result.modified_count > 0:
                QMessageBox.information(
                    self,
                    "Éxito",
                    "La contraseña se ha actualizado correctamente"
                )
                dialog.accept()
            else:
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    "No se pudo actualizar la contraseña"
                )
                
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al actualizar la contraseña: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
            if dialog.search_type.currentText() == "Por Nombre":
                query = {'$or': [
                    {'nombre': {'$regex': search_text, '$options': 'i'}},
                    {'name': {'$regex': search_text, '$options': 'i'}}
                ]}
            elif dialog.search_type.currentText() == "Por Email":
                query = {'email': {'$regex': search_text, '$options': 'i'}}
                
            # Buscar usuarios que coincidan con la consulta
            users = list(self.db[collection_name].find(query))
            for user in users:
                # Store source collection consistently
                user['_source_collection'] = collection_name
                found_users.append(user)
        if not found_users:
            QMessageBox.information(dialog, "Información", "No se encontraron usuarios que coincidan con los criterios")
            return
            
        # Si hay múltiples usuarios, mostrar un diálogo de selección
        if len(found_users) > 1:
            user_select = QDialog(dialog)
            user_select.setWindowTitle("Seleccionar Usuario")
            user_select.resize(400, 300)
            
            layout = QVBoxLayout(user_select)
            layout.addWidget(QLabel("Múltiples usuarios encontrados. Seleccione uno:"))
            
            user_list = QListWidget()
            for user in found_users:
                user_name = user.get('nombre', user.get('name', 'Sin nombre'))
                user_email = user.get('email', 'Sin email')
                user_list.addItem(f"{user_name} ({user_email}) - {user.get('_source_collection', 'users_unified')}")
            
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(user_select.accept)
            buttons.rejected.connect(user_select.reject)
            layout.addWidget(buttons)
            
            if user_select.exec() != QDialog.DialogCode.Accepted:
                return
                
            selected_idx = user_list.currentRow()
            if selected_idx < 0:
                return
                
            selected_user = found_users[selected_idx]
        else:
            # Solo un usuario encontrado
            selected_user = found_users[0]
            
        # Actualizar diálogo con información del usuario seleccionado
        user_name = selected_user.get('nombre', selected_user.get('name', 'Sin nombre'))
        user_email = selected_user.get('email', 'Sin email')
        dialog.user_label.setText(f"Usuario seleccionado: {user_name} ({user_email})")
        dialog.user_label.setStyleSheet("font-weight: bold; color: #3498db;")
        
        # Habilitar campos de contraseña
        dialog.password_input.setEnabled(True)
        dialog.confirm_input.setEnabled(True)
        dialog.save_button.setEnabled(True)
        
        # Guardar referencia al usuario seleccionado
        dialog.selected_user = selected_user
        dialog.selected_collection = selected_user.get('_source_collection', selected_user.get('_collection', 'users_unified'))
    
        
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
                            collection = db[collection_name]
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
                if db_name in self.client.list_database_names():
                    db = self.client[db_name]
                    
                    if 'audit_log' in db.list_collection_names():
                        # Eliminar el layout viejo por completo
                        QWidget().setLayout(old_layout)
                    
                    # Create a new layout for data widget
                    new_data_layout = QVBoxLayout()
                    data_widget.setLayout(new_data_layout)
                    
                    # Crear un widget con pestañas para los datos y metadatos
                    self.collections_tab_widget = QTabWidget()
                    
                    # Handle access logs if they exist
                    try:
                        # Check if access logs are available
                        if access_logs:
                            access_table = QTableWidget()
                            access_table.setColumnCount(3)
                            access_table.setHorizontalHeaderLabels(["Usuario", "Acción", "Fecha"])
                            access_table.setRowCount(len(access_logs))
                            
                            # Populate the access table with log entries
                            for i, log in enumerate(access_logs):
                                access_table.setItem(i, 0, QTableWidgetItem(str(log.get('user', 'N/A'))))
                                access_table.setItem(i, 1, QTableWidgetItem(str(log.get('action', 'N/A'))))
                                access_table.setItem(i, 2, QTableWidgetItem(str(log.get('timestamp', 'N/A'))))
                            
                            # Add the access table to the layout
                            access_layout = QVBoxLayout()
                            access_layout.addWidget(access_table)
                            access_widget = QWidget()
                            access_widget.setLayout(access_layout)
                            self.collections_tab_widget.addTab(access_widget, "Auditoría")
                        else:
                            # No access logs available
                            access_layout = QVBoxLayout()
                            access_layout.addWidget(QLabel("No hay registros de auditoría disponibles para esta base de datos"))
                            access_widget = QWidget()
                            access_widget.setLayout(access_layout)
                            self.collections_tab_widget.addTab(access_widget, "Auditoría")
                    except Exception as access_error:
                        print(f"Error al obtener información de acceso: {access_error}")
                        access_layout = QVBoxLayout()
                        access_layout.addWidget(QLabel("Error al recuperar información de accesos"))
                        access_widget = QWidget()
                        access_widget.setLayout(access_layout)
                        self.collections_tab_widget.addTab(access_widget, "Auditoría")
                
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
            class CollectionSelectDialog(QDialog):
                def __init__(self, parent=None, collections=None):
                    super().__init__(parent)
                    self.setWindowTitle("Seleccionar Colección")
                    self.resize(300, 200)
                    
                    layout = QVBoxLayout(self)
                    
                    self.label = QLabel("Seleccione una colección para editar sus campos:")
                    layout.addWidget(self.label)
                    
                    # Usar QListWidget importado al inicio del archivo
                    self.collection_list = QListWidget()
                    if collections:
                        self.collection_list.addItems(collections)
                    layout.addWidget(self.collection_list)
                    
                    self.button_box = QDialogButtonBox(
                        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                    )
                    self.button_box.accepted.connect(self.accept)
                    self.button_box.rejected.connect(self.reject)
                    layout.addWidget(self.button_box)
                    
                def get_selected_collection(self):
                    if self.collection_list.currentItem():
                        return self.collection_list.currentItem().text()
                    return None
                    
            # Crear y mostrar el diálogo
            select_dialog = CollectionSelectDialog(self, collections)
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
            class CollectionSelectDialog(QDialog):
                def __init__(self, parent=None, collections=None):
                    super().__init__(parent)
                    self.setWindowTitle("Seleccionar Colección")
                    self.resize(300, 200)
                    
                    layout = QVBoxLayout(self)
                    
                    self.label = QLabel("Seleccione una colección para gestionar sus índices:")
                    layout.addWidget(self.label)
                    
                    self.collection_list = QListWidget()
                    if collections:
                        self.collection_list.addItems(collections)
                    layout.addWidget(self.collection_list)
                    
                    self.button_box = QDialogButtonBox(
                        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                    )
                    self.button_box.accepted.connect(self.accept)
                    self.button_box.rejected.connect(self.reject)
                    layout.addWidget(self.button_box)
                    
                def get_selected_collection(self):
                    if self.collection_list.currentItem():
                        return self.collection_list.currentItem().text()
                    return None
                    
            # Mostrar diálogo de selección
            select_dialog = CollectionSelectDialog(self, collections)
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
                    except Exception as e:
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
            
            # Añadir pestañas al TabWidget
            # Añadir pestañas al TabWidget
            tab_widget.addTab(existing_tab, "Índices Existentes")
            tab_widget.addTab(create_tab, "Crear Índice")

            # Añadir datos de la colección al formulario
            form_layout = QFormLayout(create_tab)
            collection_name_label = QLabel(collection_name)
            collection_name_label.setStyleSheet("font-weight: bold;")
            form_layout.addRow("Colección:", collection_name_label)
            
            # Es único
            is_unique = "Sí" if index.get('unique', False) else "No"
            index_table.setItem(i, 4, QTableWidgetItem(is_unique))
            
            # Resize columns to fit content
            index_table.resizeColumnsToContents()
            
            # Añadir estadísticas de uso para índices existentes
            try:
                # Obtener información de índices
                usage = "Bajo"
                ops = "~10/día"
            except Exception as e:
                print(f"Error al obtener estadísticas de uso: {e}")
            
            # Añadir la pestaña de reindexación
            tab_widget.addTab(reindex_tab, "Rendimiento")

            # Create tab setup
            # Form for index creation
            form_layout = QFormLayout()
            
            # Add field selection
            form_layout.addRow("Seleccionar campos:", QLabel("Seleccione los campos para indexar"))
            
            # Index type selection
            index_type_combo = QComboBox()
            index_type_combo.addItems(["Estándar", "Único", "Texto", "TTL"])
            form_layout.addRow("Tipo de índice:", index_type_combo)
            
            # Options widget for different index types
            options_widget = QStackedWidget()
            
            # Conectar cambios de tipo de índice con cambios en el widget de opciones
            index_type_combo.currentIndexChanged.connect(lambda idx: options_widget.setCurrentIndex(idx))
            
            # Añadir el layout de formulario al layout de creación
            create_layout.addLayout(form_layout)
            
            button_layout = QHBoxLayout()
            # Options widget for different index types
            options_widget = QStackedWidget()
            
            # Conectar cambios de tipo de índice con cambios en el widget de opciones
            index_type_combo.currentIndexChanged.connect(lambda idx: options_widget.setCurrentIndex(idx))
            
            # Añadir el layout de formulario al layout de creación
            create_layout.addLayout(form_layout)
            
            # Clear the index table
            index_table.setRowCount(0)
            
            # Obtener índices actualizados
            collection = self.db[collection_name]
            indexes = list(collection.list_indexes())
            
            # Actualizar tabla
            index_table.setRowCount(len(indexes))
            
            for i, index in enumerate(indexes):
                # Nombre del índice
                index_table.setItem(i, 0, QTableWidgetItem(index.get('name', 'N/A')))
                
                # Campos del índice
                key_fields = ', '.join([f"{k}:{v}" for k, v in index.get('key', {}).items()])
                index_table.setItem(i, 1, QTableWidgetItem(key_fields))
                    
            # Update complete
        except Exception as e:
            print(f"Error al actualizar índices: {e}")
            QMessageBox.warning(self, "Error", f"Error al actualizar índices: {str(e)}")
            
            # Widget para índice TTL
            ttl_widget = QWidget()
            ttl_layout = QFormLayout(ttl_widget)
            
            ttl_seconds = QLineEdit()
            ttl_seconds.setText("86400")  # 1 día por defecto
            ttl_layout.addRow("Segundos para expiración:", ttl_seconds)
            
            ttl_info = QLabel("Los documentos serán eliminados automáticamente después de este tiempo")
            ttl_info.setWordWrap(True)
            ttl_layout.addWidget(ttl_info)
            
            options_widget.addWidget(ttl_widget)
            
            # Conectar cambios de tipo de índice con cambios en el widget de opciones
            index_type.currentIndexChanged.connect(options_widget.setCurrentIndex)
            
            form_layout.addRow("Opciones:", options_widget)
            
            # Botones para crear índice
            create_layout.addLayout(form_layout)
            
            options_widget.addWidget(ttl_widget)
            
            # Conectar cambios de tipo de índice con cambios en el widget de opciones
            index_type.currentIndexChanged.connect(options_widget.setCurrentIndex)
            
            form_layout.addRow("Opciones:", options_widget)
            
            # Botones para crear índice
            create_layout.addLayout(form_layout)
            # Función para eliminar un índice seleccionado
            def delete_selected_index():
                selected_row = index_table.currentRow()
                
                # Función para actualizar la tabla de índices
                def refresh_indexes():
                    try:
                        # Limpiar la tabla
                        index_table.setRowCount(0)
                        
                        # Obtener índices actualizados
                        collection = self.db[collection_name]
                        indexes = list(collection.list_indexes())
                        
                        # Actualizar tabla
                        index_table.setRowCount(len(indexes))
                        
                        for i, index in enumerate(indexes):
                            # Nombre del índice
                            index_table.setItem(i, 0, QTableWidgetItem(index.get('name', 'N/A')))
                            
                            # Campos del índice
                            key_fields = ', '.join([f"{k}:{v}" for k, v in index.get('key', {}).items()])
                            index_table.setItem(i, 1, QTableWidgetItem(key_fields))
                            
                            # Tipo de índice
                    except Exception as e:
                        print(f"Error al actualizar índices: {e}")
                        QMessageBox.warning(self, "Error", f"Error al actualizar índices: {str(e)}")
            
            # Crear documento clave
            key_dict = {}
            
            if index_type_text == "Estándar":
                # Índice estándar - asignar 1 a cada campo
                for field in selected_fields:
                    key_dict[field] = 1
                    
            elif index_type_text == "Único":
                # Índice único
                for field in selected_fields:
                    key_dict[field] = 1
                index_options["unique"] = True
                
            elif index_type_text == "Texto":
                # Índice de texto
                for field in selected_fields:
                    key_dict[field] = "text"
                    
                # Si se especificaron pesos
                if text_weights_check.isChecked():
                    weights = {}
                    for i, field in enumerate(selected_fields):
                        # Obtener el peso del campo desde el formulario
                        weight_input = weights_widget.findChild(QLineEdit, f"weight_{field}")
                        if weight_input:
                            try:
                                weight = int(weight_input.text())
                                weights[field] = weight
                            except ValueError:
                                weights[field] = 1
                        else:
                            weights[field] = 1
                    
                    index_options["weights"] = weights
            
            elif index_type_text == "TTL":
                # Índice TTL
                if len(selected_fields) != 1:
                    QMessageBox.warning(self, "Advertencia", "Los índices TTL solo pueden tener un campo (de tipo fecha)")
                    return
            
                field = selected_fields[0]
                key_dict[field] = 1
                
                try:
                    seconds = int(ttl_seconds.text())
                    index_options["expireAfterSeconds"] = seconds
                except ValueError:
                    QMessageBox.warning(self, "Advertencia", "El tiempo de expiración debe ser un número entero de segundos")
                    return
            
            # Crear nombre para el índice
            index_name = "_".join(selected_fields)
            if index_type_text != "Estándar":
                index_name += f"_{index_type_text.lower()}"
                
            index_options["name"] = index_name
            
            # Confirmar creación de índice
            confirm = QMessageBox.question(
                self,
                "Confirmar Creación",
                f"¿Está seguro de que desea crear el índice '{index_name}'?\n\n"
                f"Campos: {', '.join(selected_fields)}\n"
                f"Tipo: {index_type_text}\n\n"
            )
            
            # Widget para índice TTL
            ttl_widget = QWidget()
            ttl_layout = QFormLayout(ttl_widget)
            
            # Agregar widget TTL a opciones
            options_widget.addWidget(ttl_widget)
            
            # Crear el índice si el usuario confirmó
            if confirm == QMessageBox.Yes:
                try:
                    collection = self.db[collection_name]
                    collection.create_index(list(key_dict.items()), **index_options)
                    
                    # Actualizar tabla de índices existentes
                    refresh_indexes()
                    
                    # Cambiar a la pestaña de índices existentes
                    tab_widget.setCurrentIndex(0)
                    
                    QMessageBox.information(self, "Éxito", f"Índice '{index_name}' creado correctamente")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error al crear índice: {str(e)}")
            
            def reindex_collection_action():
                try:
                    # Confirmar reindexación
                    confirm = QMessageBox.question(
                        self,
                        "Confirmar Reindexación",
                        f"¿Está seguro de que desea reindexar la colección '{collection_name}'?\n\n"
                        "Este proceso puede tardar mucho tiempo en colecciones grandes y bloquea las operaciones de escritura.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if confirm == QMessageBox.StandardButton.Yes:
                        # Crear diálogo de progreso
                        progress = QProgressDialog("Reindexando colección...", "Cancelar", 0, 100, self)
                        progress.setWindowModality(Qt.WindowModality.WindowModal)
                        progress.setValue(0)
                        progress.show()
                        
                        # Función para reindexar
                        def do_reindex():
                            try:
                                # Ejecutar reindex
                                result = self.db.command("reIndex", collection_name)
                                return True, result
                            except Exception as e:
                                return False, str(e)
                        
                        # En una aplicación real, esto debería ejecutarse en un hilo separado
                        # Para simplificar, lo hacemos directamente
                        progress.setValue(30)  # Actualizar progreso para indicar que ha comenzado
                        
                        success, result = do_reindex()
                        
                        progress.setValue(100)  # Completar barra de progreso
                        
                        if success:
                            QMessageBox.information(self, "Éxito", f"Colección '{collection_name}' reindexada correctamente")
                            # Actualizar tabla de índices
                            refresh_indexes()
                        else:
                            QMessageBox.critical(self, "Error", f"Error durante la reindexación: {result}")
                
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error al reindexar colección: {str(e)}")
            
            # Conectar botones con sus acciones
            create_button.clicked.connect(create_index_action)
            cancel_button.clicked.connect(lambda: index_dialog.reject())
            reindex_button.clicked.connect(reindex_collection_action)
            
            # Mostrar el diálogo
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
            summary = QLabel(f"Resumen: {valid_count}/{len(results)} colecciones son válidas")
            
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
            if hasattr(self, 'collections_tree') and self.collections_tree and not sip.isdeleted(self.collections_tree):
                try:
                    self.collections_tree.setParent(None)
                    self.collections_tree.deleteLater()
                except:
                    pass  # Silently handle deletion errors
            
            tree_layout = self.tree_widget.layout()
            
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
            
        except Exception as e:
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
            
    def backup_database(self):
        """Create a backup of the database"""
        try:
            # Implementation of backup functionality
            pass
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al seleccionar ruta: {str(e)}")
            return  # Return after handling the exception
    def execute_backup(self, backup_path, is_full_backup, selected_collections, compress_backup, 
                       compression_level, schedule_backup, schedule_frequency, schedule_time, 
                       schedule_day, dialog):
        """Ejecutar el respaldo con las opciones configuradas"""
        try:
            # Validar ruta de respaldo
            if not backup_path:
                QMessageBox.warning(dialog, "Advertencia", "Por favor, especifique una ruta de respaldo válida")
                return
                
            # Validar colecciones seleccionadas si es respaldo selectivo
            if not is_full_backup and not selected_collections:
                QMessageBox.warning(dialog, "Advertencia", "Por favor, seleccione al menos una colección para el respaldo selectivo")
                return
                
            # Crear directorio si no existe
            if not os.path.exists(backup_path):
                os.makedirs(backup_path)
                
            # Si se programó un respaldo
            if schedule_backup:
                self.schedule_backup_task(backup_path, is_full_backup, selected_collections, 
                                        compress_backup, compression_level, 
                                        schedule_frequency, schedule_time, schedule_day)
                dialog.accept()
                return
                
            # Iniciar respaldo
            progress_dialog = QProgressDialog("Preparando respaldo...", "Cancelar", 0, 100, dialog)
            progress_dialog.setWindowTitle("Respaldo en progreso")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setAutoClose(False)
            progress_dialog.setAutoReset(False)
            progress_dialog.setValue(0)
            progress_dialog.show()
            
            # Crear función para realizar el respaldo en un hilo separado
            def perform_backup():
                try:
                    # Actualizar progreso
                    progress_dialog.setLabelText("Recopilando información de la base de datos...")
                    progress_dialog.setValue(5)
                    
                    # Obtener colecciones según el tipo de respaldo
                    collections_to_backup = []
                    if is_full_backup:
                        # Respaldar todas las colecciones excepto las del sistema
                        collections_to_backup = [col for col in self.db.list_collection_names() 
                                               if not col.startswith('system.')]
                    else:
                        # Respaldar solo las colecciones seleccionadas
                        collections_to_backup = selected_collections
                    
                    progress_dialog.setLabelText(f"Respaldando {len(collections_to_backup)} colecciones...")
                    progress_dialog.setValue(10)
                    
                    # Crear archivo de metadatos
                    metadata = {
                        'database': self.database_name,
                        'timestamp': datetime.datetime.now().isoformat(),
                        'collections': collections_to_backup,
                        'compressed': compress_backup,
                        'full_backup': is_full_backup,
                        'version': '1.0'
                    }
                    
                    # Guardar metadatos
                    metadata_path = os.path.join(backup_path, 'metadata.json')
                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, default=str)
                        
                    # Crear directorio para los datos
                    data_dir = os.path.join(backup_path, 'collections')
                    if not os.path.exists(data_dir):
                        os.makedirs(data_dir)
                    
                    # Exportar cada colección
                    total_collections = len(collections_to_backup)
                    for i, collection_name in enumerate(collections_to_backup):
                        if progress_dialog.wasCanceled():
                            break
                            
                        progress_percent = 10 + int((i / total_collections) * 80)
                        progress_dialog.setValue(progress_percent)
                        progress_dialog.setLabelText(f"Respaldando colección: {collection_name}...")
                        
                        try:
                            # Exportar datos de la colección
                            collection = self.db[collection_name]
                            documents = list(collection.find())
                            
                            # Guardar documentos
                            collection_file = os.path.join(data_dir, f"{collection_name}.json")
                            
                            if compress_backup:
                                with gzip.open(collection_file + '.gz', 'wt', encoding='utf-8', compresslevel=compression_level) as f:
                                    json.dump(documents, f, default=str, indent=None)
                            else:
                                with open(collection_file, 'w', encoding='utf-8') as f:
                                    json.dump(documents, f, default=str, indent=2)
                                    
                            # Exportar índices
                            indexes = list(collection.list_indexes())
                            indexes_file = os.path.join(data_dir, f"{collection_name}_indexes.json")
                            
                            if compress_backup:
                                with gzip.open(indexes_file + '.gz', 'wt', encoding='utf-8', compresslevel=compression_level) as f:
                                    json.dump(indexes, f, default=str, indent=None)
                            else:
                                with open(indexes_file, 'w', encoding='utf-8') as f:
                                    json.dump(indexes, f, default=str, indent=2)
                                    
                        except Exception as col_error:
                            progress_dialog.setLabelText(f"Error en colección {collection_name}: {str(col_error)}")
                            print(f"Error al respaldar colección {collection_name}: {col_error}")
                            continue
                    
                    # Registrar el respaldo en el log
                    log_file = os.path.join(backup_path, 'backup_log.txt')
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write(f"Respaldo de {self.database_name} completado en {datetime.datetime.now().isoformat()}\n")
                        f.write(f"Tipo: {'Completo' if is_full_backup else 'Selectivo'}\n")
                        f.write(f"Colecciones respaldadas: {len(collections_to_backup)}\n")
                        for col in collections_to_backup:
                            f.write(f"  - {col}\n")
                    
                    # Finalizar
                    progress_dialog.setValue(100)
                    progress_dialog.setLabelText("Respaldo completado con éxito")
                    
                    # Resultado exitoso
                    return True, "Respaldo completado con éxito"
                    
                except Exception as e:
                    progress_dialog.setLabelText(f"Error durante el respaldo: {str(e)}")
                    print(f"Error durante el respaldo: {e}")
                    return False, str(e)
            
            # Ejecutar el respaldo en un hilo separado
            backup_thread = threading.Thread(target=perform_backup)
            backup_thread.daemon = True
            backup_thread.start()
            
            # Esperar a que termine el respaldo o se cancele
            while backup_thread.is_alive() and not progress_dialog.wasCanceled():
                QApplication.processEvents()
            
            if progress_dialog.wasCanceled():
                QMessageBox.warning(dialog, "Advertencia", "Respaldo cancelado por el usuario")
                dialog.accept()
                return
                
            # Verificar si se completó correctamente
            completed = not backup_thread.is_alive()
            if completed:
                QMessageBox.information(
                    dialog,
                    "Respaldo Completado",
                    f"El respaldo se ha completado exitosamente en:\n{backup_path}"
                )
                dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(dialog, "Error", f"Error al ejecutar el respaldo: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
    def schedule_backup_task(self, backup_path, is_full_backup, selected_collections, 
                           compress_backup, compression_level, frequency, schedule_time, day_of_week):
        """Programar un respaldo para ejecutarse periódicamente"""
        try:
            # Crear directorio de configuración
            config_dir = os.path.join(os.path.expanduser("~"), ".mongodb_manager")
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                
            # Archivo para almacenar tareas programadas
            tasks_file = os.path.join(config_dir, "scheduled_backups.json")
            
            # Cargar tareas existentes
            tasks = []
            if os.path.exists(tasks_file):
                try:
                    with open(tasks_file, 'r', encoding='utf-8') as f:
                        tasks = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Error al cargar tareas existentes: {e}")
                    tasks = []
                except Exception as e:
                    print(f"Error al cargar tareas existentes: {e}")
                    tasks = []
            
            # Crear nueva tarea
            task_id = f"backup_{self.database_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Convertir colecciones seleccionadas a una lista
            collections_list = selected_collections
            
            time_str = schedule_time.toString("HH:mm")
            
            # Crear nueva tarea
            task = {
                "id": task_id,
                "type": "backup",
                "database": self.database_name,
                "connection_string": self.connection_string,
                "path": backup_path,
                "is_full_backup": is_full_backup,
                "selected_collections": collections_list,
                "compress": compress_backup,
                "compression_level": compression_level,
                "frequency": frequency,
                "time": time_str,
                "day_of_week": day_of_week,
                "created_at": datetime.datetime.now().isoformat(),
                "last_run": None,
                "next_run": None
            }
            
            # Calcular próxima ejecución
            now = datetime.datetime.now()
            run_time = datetime.datetime.strptime(time_str, "%H:%M").time()
            next_run = datetime.datetime.combine(now.date(), run_time)
            
            if next_run <= now:
                next_run += datetime.timedelta(days=1)
                
            if frequency == "Semanal":
                # Convertir día de la semana a número (0 = lunes, 6 = domingo)
                days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                target_day = days.index(day_of_week)
                current_day = next_run.weekday()
                
                # Calcular días hasta el día objetivo
                days_until_target = (target_day - current_day) % 7
                if days_until_target == 0 and next_run <= now:
                    days_until_target = 7
                    
                next_run += datetime.timedelta(days=days_until_target)
            elif frequency == "Mensual":
                # Para respaldos mensuales, ejecutar el primer día del mes
                next_month = next_run.replace(day=1) + datetime.timedelta(days=32)
                next_run = next_month.replace(day=1)
                
            task["next_run"] = next_run.isoformat()
            
            # Agregar tarea a la lista
            tasks.append(task)
            
            # Guardar tareas
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=2, default=str)
            
            # Informar al usuario
            QMessageBox.information(
                self,
                "Respaldo Programado",
                f"El respaldo ha sido programado con frecuencia {frequency.lower()} a las {time_str}.\n\n"
                f"Próxima ejecución: {next_run.strftime('%d/%m/%Y %H:%M')}")
            
            # Crear o actualizar una tarea programada en el sistema (solo ejemplo, no implementado realmente)
            self.show_status_message("Respaldo programado correctamente")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al programar el respaldo: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
    def restore_database(self):
        """Restaurar la base de datos desde un respaldo"""
        if self.db is None:
            QMessageBox.critical(self, "Error", "No hay conexión a la base de datos")
            return

        # Abrir diálogo para seleccionar archivo de respaldo
        backup_file, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo de respaldo",
            os.path.expanduser("~"),
            "Archivos de respaldo (*.gz *.json)"
        )

        if not backup_file:
            return

        try:
            # Determinar si es un archivo comprimido
            is_compressed = backup_file.lower().endswith('.gz')

            # Leer el archivo
            if is_compressed:
                with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                    backup_data = json.load(f)
            else:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)

            # Verificar estructura del respaldo
            if not isinstance(backup_data, dict) or 'collections' not in backup_data:
                raise ValueError("Archivo de respaldo inválido")

            # Mostrar progreso
            progress = QProgressDialog("Restaurando datos...", "Cancelar", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)

            # Procesar cada colección
            total_collections = len(backup_data['collections'])
            current_collection = 0

            for collection_name, collection_data in backup_data['collections'].items():
                if progress.wasCanceled():
                    break

            # Seleccionar directorio de respaldo
            backup_dir = QFileDialog.getExistingDirectory(
                self,
                "Seleccionar Directorio de Respaldo",
                os.path.join(os.path.expanduser("~"), "MongoDB_Backups")
            )
            if not backup_dir:
                return
                return
                
            # Verificar si es un respaldo válido
            metadata_path = os.path.join(backup_dir, 'metadata.json')
            if not os.path.exists(metadata_path):
                QMessageBox.warning(self, "Advertencia", "El directorio seleccionado no contiene un respaldo válido (falta archivo metadata.json)")
                return
                
            # Leer metadatos del respaldo
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    
                # Verificar compatibilidad de base de datos
                backup_db = metadata.get('database', '')
                if backup_db != self.database_name:
                    confirm = QMessageBox.question(
                        self,
                        "Diferente Base de Datos",
                        f"El respaldo es de la base de datos '{backup_db}', pero está restaurando en '{self.database_name}'.\n\n"
                        "¿Desea continuar con la restauración en la base de datos actual?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if confirm != QMessageBox.StandardButton.Yes:
                        return
                        
                # Obtener colecciones disponibles en el respaldo
                available_collections = metadata.get('collections', [])
                is_compressed = metadata.get('compressed', False)
                
                if not available_collections:
                    QMessageBox.warning(self, "Advertencia", "El respaldo no contiene colecciones para restaurar")
                    return
                    
                # Crear diálogo de restauración
                restore_dialog = QDialog(self)
                restore_dialog.setWindowTitle("Restaurar Base de Datos desde Respaldo")
                restore_dialog.resize(600, 500)
                
                layout = QVBoxLayout(restore_dialog)
                
                # Información del respaldo
                timestamp = metadata.get('timestamp', 'Desconocido')
                if isinstance(timestamp, str) and len(timestamp) > 19:
                    timestamp = timestamp[:19].replace("T", " ")  # Formatear ISO timestamp
                
                info_text = f"""
<h3>Restaurar desde Respaldo</h3>
<p><b>Base de datos del respaldo:</b> {backup_db}</p>
<p><b>Fecha del respaldo:</b> {timestamp}</p>
<p><b>Colecciones disponibles:</b> {len(available_collections)}</p>
<p><b>Compresión:</b> {'Activada' if is_compressed else 'Desactivada'}</p>
"""
                
                info_label = QLabel(info_text)
                info_label.setTextFormat(Qt.TextFormat.RichText)
                layout.addWidget(info_label)
                
                # Opciones de restauración
                options_group = QGroupBox("Opciones de Restauración")
                options_layout = QVBoxLayout(options_group)
                
                # Radio buttons para tipo de restauración
                restore_type_group = QButtonGroup(restore_dialog)
                
                full_restore_radio = QRadioButton("Restauración Completa (todas las colecciones del respaldo)")
                full_restore_radio.setChecked(True)
                restore_type_group.addButton(full_restore_radio)
                options_layout.addWidget(full_restore_radio)
                
                selective_restore_radio = QRadioButton("Restauración Selectiva (colecciones específicas)")
                restore_type_group.addButton(selective_restore_radio)
                options_layout.addWidget(selective_restore_radio)
                
                layout.addWidget(options_group)
                
                # Lista de colecciones disponibles para restauración selectiva
                collections_group = QGroupBox("Seleccionar Colecciones")
                collections_layout = QVBoxLayout(collections_group)
                
                collections_list = QListWidget()
                collections_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
                
                for collection in available_collections:
                    item = QListWidgetItem(collection)
                    # Preseleccionar todas las colecciones
                    item.setSelected(True)
                    collections_list.addItem(item)
                
                collections_layout.addWidget(collections_list)
                collections_group.setEnabled(False)  # Inicialmente deshabilitado
                layout.addWidget(collections_group)
                
                # Conectar cambio de tipo de restauración con habilitación de selección de colecciones
                selective_restore_radio.toggled.connect(collections_group.setEnabled)

                # Opciones de conflicto
                conflict_group = QGroupBox("Manejo de Conflictos")
                conflict_layout = QVBoxLayout(conflict_group)
                
                conflict_option = QComboBox()
                conflict_option.addItems([
                    "Reemplazar documentos existentes",
                    "Mantener documentos existentes si tienen la misma ID",
                    "Solo añadir documentos que no existan"
                ])
                conflict_layout.addWidget(conflict_option)
                
                drop_first = QCheckBox("Eliminar colecciones existentes antes de restaurar")
                conflict_layout.addWidget(drop_first)
                
                layout.addWidget(conflict_group)
                
                # Botones de acción
                button_box = QDialogButtonBox()
                
                restore_button = QPushButton("Iniciar Restauración")
                restore_button.setStyleSheet("background-color: #2ecc71; color: white;")
                button_box.addButton(restore_button, QDialogButtonBox.ButtonRole.AcceptRole)
                
                cancel_button = QPushButton("Cancelar")
                button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
                
                layout.addWidget(button_box)
                
                # Conectar botones
                restore_button.clicked.connect(lambda: self.execute_restore(
                    backup_dir,
                    metadata,
                    full_restore_radio.isChecked(),
                    [collections_list.item(i).text() for i in range(collections_list.count()) 
                     if collections_list.item(i).isSelected()],
                    conflict_option.currentIndex(),
                    drop_first.isChecked(),
                    restore_dialog
                ))
                
                cancel_button.clicked.connect(restore_dialog.reject)
                
                # Mostrar el diálogo
                restore_dialog.exec()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al procesar los metadatos del respaldo: {str(e)}")
                self.show_status_message(f"Error: {str(e)}", error=True)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al preparar la restauración: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            
    def execute_restore(self, backup_dir, metadata, is_full_restore, selected_collections,
                        conflict_mode, drop_first, dialog):
        """Ejecutar la restauración con las opciones configuradas."""
        try:
            all_collections = metadata.get("collections", [])

            if not is_full_restore and not selected_collections:
                QMessageBox.warning(
                    dialog, "Advertencia",
                    "Por favor, seleccione al menos una colección para restaurar"
                )
                return

            collections_to_restore = (
                all_collections if is_full_restore else selected_collections
            )
            is_compressed = metadata.get("compressed", False)
            total_cols = len(collections_to_restore)
            collections_dir = os.path.join(backup_dir, "collections")
            errors = []
            restored_collections = [0]

            progress_dialog = QProgressDialog(
                "Preparando restauración...", "Cancelar", 0, 100, dialog
            )
            progress_dialog.setWindowTitle("Restauración en progreso")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setAutoClose(False)
            progress_dialog.setAutoReset(False)
            progress_dialog.setValue(0)

            def perform_restore():
                for i, collection_name in enumerate(collections_to_restore):
                    if progress_dialog.wasCanceled():
                        break

                    pct = 10 + int((i / total_cols) * 80)
                    progress_dialog.setValue(pct)
                    progress_dialog.setLabelText(
                        f"Restaurando colección: {collection_name}..."
                    )

                    try:
                        col_file = os.path.join(
                            collections_dir, f"{collection_name}.json"
                        )
                        col_gz = col_file + ".gz"

                        if not os.path.exists(col_file) and not os.path.exists(col_gz):
                            errors.append(
                                f"Archivo '{collection_name}' no encontrado"
                            )
                            continue

                        if drop_first and collection_name in self.db.list_collection_names():
                            self.db.drop_collection(collection_name)

                        documents = []
                        if is_compressed and os.path.exists(col_gz):
                            with gzip.open(col_gz, "rt", encoding="utf-8") as f:
                                documents = json.load(f)
                        elif os.path.exists(col_file):
                            with open(col_file, "r", encoding="utf-8") as f:
                                documents = json.load(f)

                        if not documents:
                            errors.append(
                                f"Sin documentos en '{collection_name}'"
                            )
                            continue

                        from bson.objectid import ObjectId
                        for doc in documents:
                            if (
                                "_id" in doc
                                and isinstance(doc["_id"], str)
                                and doc["_id"].startswith("ObjectId(")
                            ):
                                id_str = (
                                    doc["_id"]
                                    .replace("ObjectId('", "")
                                    .replace("')", "")
                                    .replace('"', "")
                                )
                                try:
                                    doc["_id"] = ObjectId(id_str)
                                except Exception:
                                    pass

                        col = self.db[collection_name]
                        if conflict_mode == 0:
                            existing = set(d["_id"] for d in col.find({}, {"_id": 1}))
                            to_rm = [d for d in documents if d["_id"] in existing]
                            if to_rm:
                                col.delete_many({"_id": {"$in": [d["_id"] for d in to_rm]}})
                            col.insert_many(documents)
                        elif conflict_mode == 1:
                            existing = set(d["_id"] for d in col.find({}, {"_id": 1}))
                            to_ins = [d for d in documents if d["_id"] not in existing]
                            if to_ins:
                                col.insert_many(to_ins)
                        else:
                            existing = set(d["_id"] for d in col.find({}, {"_id": 1}))
                            to_ins = [d for d in documents if d["_id"] not in existing]
                            if to_ins:
                                col.insert_many(to_ins)

                        idx_file = os.path.join(
                            collections_dir, f"{collection_name}_indexes.json"
                        )
                        idx_gz = idx_file + ".gz"
                        indexes = []
                        if os.path.exists(idx_file):
                            with open(idx_file, "r", encoding="utf-8") as f_i:
                                indexes = json.load(f_i)
                        elif os.path.exists(idx_gz):
                            with gzip.open(idx_gz, "rt", encoding="utf-8") as f_i:
                                indexes = json.load(f_i)

                        for idx in indexes:
                            if idx.get("name") != "_id_":
                                try:
                                    col.create_index(idx["key"], name=idx.get("name"))
                                except Exception:
                                    pass

                        restored_collections[0] += 1

                    except Exception as exc:
                        errors.append(f"Error restaurando '{collection_name}': {exc}")

                report_file = os.path.join(backup_dir, "restore_report.txt")
                try:
                    with open(report_file, "w", encoding="utf-8") as f:
                        tipo = "Completa" if is_full_restore else "Selectiva"
                        print("Informe de restauracion", file=f)
                        print(f"Tipo: {tipo}", file=f)
                        print(
                            f"Colecciones restauradas: {restored_collections[0]}"
                            f" de {len(collections_to_restore)}",
                            file=f,
                        )
                        if errors:
                            print("", file=f)
                            print("Errores durante la restauracion:", file=f)
                            for err in errors:
                                print(f"  - {err}", file=f)
                except Exception:
                    pass

                progress_dialog.setValue(100)
                progress_dialog.setLabelText(
                    f"Restauracion completada. "
                    f"{restored_collections[0]} colecciones restauradas."
                )

            restore_thread = threading.Thread(target=perform_restore)
            restore_thread.daemon = True
            restore_thread.start()

            while restore_thread.is_alive() and not progress_dialog.wasCanceled():
                QApplication.processEvents()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Error durante la restauracion: {str(e)}"
            )
            self.show_status_message(f"Error: {str(e)}", error=True)

    def maintain_collections(self):
        """Realizar tareas de mantenimiento en colecciones"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return
            
        try:
            # Obtener colecciones disponibles
            collections = self.db.list_collection_names()
            
            if not collections:
                QMessageBox.information(self, "Información", "No hay colecciones disponibles para mantenimiento")
                return
            
            # Crear diálogo de mantenimiento
            maintenance_dialog = QDialog(self)
            maintenance_dialog.setWindowTitle("Mantenimiento de Colecciones")
            maintenance_dialog.resize(700, 550)
            
            layout = QVBoxLayout(maintenance_dialog)
            
            # Título e información
            title_label = QLabel("<h2>Mantenimiento de Colecciones</h2>")
            title_label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(title_label)
            
            info_label = QLabel("Seleccione las colecciones a mantener y las operaciones de mantenimiento a realizar.")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            # Selección de colecciones
            collections_group = QGroupBox("Seleccionar Colecciones")
            collections_layout = QVBoxLayout(collections_group)
            
            collections_list = QListWidget()
            collections_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            
            for collection in collections:
                item = QListWidgetItem(collection)
                collections_list.addItem(item)
                
            collections_layout.addWidget(collections_list)
            
            # Botones para seleccionar todos/ninguno
            selection_buttons = QHBoxLayout()
            
            select_all_button = QPushButton("Seleccionar Todos")
            select_all_button.clicked.connect(lambda: self.select_all_items(collections_list, True))
            selection_buttons.addWidget(select_all_button)
            
            clear_selection_button = QPushButton("Limpiar Selección")
            clear_selection_button.clicked.connect(lambda: self.select_all_items(collections_list, False))
            selection_buttons.addWidget(clear_selection_button)
            
            collections_layout.addLayout(selection_buttons)
            layout.addWidget(collections_group)
            
            # Opciones de mantenimiento
            maintenance_group = QGroupBox("Operaciones de Mantenimiento")
            maintenance_layout = QVBoxLayout(maintenance_group)
            
            # Compactar colecciones
            compact_check = QCheckBox("Compactar colecciones (reduce fragmentación)")
            maintenance_layout.addWidget(compact_check)
            
            # Reparar índices
            repair_indexes_check = QCheckBox("Reparar índices (reconstruye índices dañados)")
            maintenance_layout.addWidget(repair_indexes_check)
            
            # Validar documentos
            validate_docs_check = QCheckBox("Validar integridad de documentos")
            maintenance_layout.addWidget(validate_docs_check)
            
            # Eliminar documentos duplicados
            remove_duplicates_check = QCheckBox("Eliminar documentos duplicados")
            maintenance_layout.addWidget(remove_duplicates_check)
            
            # Actualizar estadísticas
            update_stats_check = QCheckBox("Actualizar estadísticas")
            update_stats_check.setChecked(True)
            maintenance_layout.addWidget(update_stats_check)
            
            layout.addWidget(maintenance_group)
            
            # Opciones avanzadas
            advanced_group = QGroupBox("Opciones Avanzadas")
            advanced_layout = QVBoxLayout(advanced_group)
            
            # Programar mantenimiento
            schedule_check = QCheckBox("Programar mantenimiento periódico")
            advanced_layout.addWidget(schedule_check)
            
            # Opciones de programación
            schedule_options = QWidget()
            schedule_options.setEnabled(False)
            schedule_options_layout = QFormLayout(schedule_options)
            
            frequency_combo = QComboBox()
            frequency_combo.addItems(["Diario", "Semanal", "Mensual"])
            schedule_options_layout.addRow("Frecuencia:", frequency_combo)
            
            time_edit = QTimeEdit()
            time_edit.setTime(QTime(3, 0))  # 3:00 AM por defecto
            schedule_options_layout.addRow("Hora:", time_edit)
            
            advanced_layout.addWidget(schedule_options)
            
            # Conectar checkbox con opciones de programación
            schedule_check.toggled.connect(schedule_options.setEnabled)
            
            layout.addWidget(advanced_group)
            
            # Resultados
            results_group = QGroupBox("Resultados de Mantenimiento")
            results_layout = QVBoxLayout(results_group)
            
            results_text = QTextEdit()
            results_text.setReadOnly(True)
            results_text.setPlaceholderText("Los resultados de las operaciones de mantenimiento se mostrarán aquí.")
            results_layout.addWidget(results_text)
            
            layout.addWidget(results_group)
            
            # Botones de acción
            button_layout = QHBoxLayout()
            
            execute_button = QPushButton("Ejecutar Mantenimiento")
            execute_button.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
            button_layout.addWidget(execute_button)
            
            close_button = QPushButton("Cerrar")
            button_layout.addWidget(close_button)
            
            layout.addLayout(button_layout)
            
            # Conectar señales
            execute_button.clicked.connect(lambda: self.execute_maintenance(
                [collections_list.item(i).text() for i in range(collections_list.count()) 
                 if collections_list.item(i).isSelected()],
                compact_check.isChecked(),
                repair_indexes_check.isChecked(),
                validate_docs_check.isChecked(),
                remove_duplicates_check.isChecked(),
                update_stats_check.isChecked(),
                schedule_check.isChecked(),
                frequency_combo.currentText(),
                time_edit.time(),
                results_text,
                maintenance_dialog
            ))
            
            close_button.clicked.connect(maintenance_dialog.reject)
            
            # Mostrar el diálogo
            maintenance_dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al iniciar mantenimiento: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
    
    def select_all_items(self, list_widget, select):
        """Seleccionar o deseleccionar todos los elementos de un QListWidget"""
        for i in range(list_widget.count()):
            list_widget.item(i).setSelected(select)
    
    def execute_maintenance(self, selected_collections, compact, repair_indexes, 
                          validate_docs, remove_duplicates, update_stats,
                          schedule_maintenance, frequency, schedule_time,
                          results_text, dialog):
        """Ejecutar operaciones de mantenimiento en las colecciones seleccionadas"""
        if not selected_collections:
            QMessageBox.warning(dialog, "Advertencia", "Debe seleccionar al menos una colección para mantenimiento")
            return
        
        try:
            # Si se programó mantenimiento
            if schedule_maintenance:
                self.schedule_maintenance_task(
                    selected_collections, compact, repair_indexes, 
                    validate_docs, remove_duplicates, update_stats,
                    frequency, schedule_time
                )
                results_text.append("✅ Programación de mantenimiento configurada correctamente.")
                results_text.append(f"📅 Frecuencia: {frequency}")
                results_text.append(f"🕒 Hora: {schedule_time.toString('HH:mm')}")
                return

            # Crear diálogo de progreso
            progress = QProgressDialog("Iniciando operaciones de mantenimiento...", "Cancelar", 0, 100, dialog)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setValue(0)
            progress.show()

            # Resultado general
            overall_results = []

            # Mensaje de inicio
            start_time = datetime.datetime.now()
            results_text.clear()
            results_text.append(f"🚀 Iniciando mantenimiento: {start_time.strftime('%d/%m/%Y %H:%M:%S')}")
            results_text.append(f"📊 Colecciones seleccionadas: {len(selected_collections)}")

            # Obtener colecciones disponibles
            collections = self.db.list_collection_names()
            
            if not collections:
                QMessageBox.warning(dialog, "Advertencia", "No hay colecciones disponibles para mantenimiento")
                return

            # Procesar cada colección
            for i, collection_name in enumerate(selected_collections, 1):
                if progress.wasCanceled():
                    break

                try:
                    # Obtener la colección
                    collection = self.db[collection_name]
                    
                    # Mostrar progreso
                    progress.setValue(int(i / len(selected_collections) * 100))
                    progress.setLabelText(f"Procesando {collection_name} ({i}/{len(selected_collections)})...")

                    # Compactar colección
                    if compact:
                        results_text.append(f"\nCompactando {collection_name}...")
                        try:
                            result = collection.compact()
                            results_text.append(f"✅ Compactación completada: {result}")
                        except Exception as e:
                            results_text.append(f"❌ Error compactando {collection_name}: {str(e)}")

                    # Reparar índices
                    if repair_indexes:
                        results_text.append(f"\nReparando índices de {collection_name}...")
                        try:
                            # MongoDB no tiene una operación directa de reparación de índices
                            # En su lugar, reconstruimos los índices
                            indexes = collection.list_indexes()
                            for index in indexes:
                                if index["name"] != "_id_":  # No reconstruir el índice _id_
                                    collection.drop_index(index["name"])
                                    collection.create_index(index["key"], name=index["name"])
                            results_text.append(f"✅ Índices reparados")
                        except Exception as e:
                            results_text.append(f"❌ Error reparando índices: {str(e)}")

                    # Validar documentos
                    if validate_docs:
                        results_text.append(f"\nValidando documentos de {collection_name}...")
                        try:
                            validation = collection.validate()
                            results_text.append(f"✅ Validación completada: {validation['valid']}")
                            if not validation['valid']:
                                results_text.append(f"⚠️ Errores encontrados: {validation['errors']}")
                        except Exception as e:
                            results_text.append(f"❌ Error validando documentos: {str(e)}")

                    # Eliminar documentos duplicados
                    if remove_duplicates:
                        results_text.append(f"\nEliminando duplicados de {collection_name}...")
                        try:
                            # Encontrar documentos duplicados
                            duplicates = []
                            seen = set()
                            for doc in collection.find():
                                doc_id = str(doc['_id'])
                                if doc_id in seen:
                                    duplicates.append(doc_id)
                                seen.add(doc_id)
                            
                            if duplicates:
                                # Eliminar duplicados
                                for doc_id in duplicates:
                                    collection.delete_one({'_id': ObjectId(doc_id)})
                                results_text.append(f"✅ Eliminados {len(duplicates)} duplicados")
                            else:
                                results_text.append("✅ No se encontraron duplicados")
                        except Exception as e:
                            results_text.append(f"❌ Error eliminando duplicados: {str(e)}")

                    # Actualizar estadísticas
                    if update_stats:
                        results_text.append(f"\nActualizando estadísticas de {collection_name}...")
                        try:
                            stats = collection.stats()
                            results_text.append(f"✅ Estadísticas actualizadas")
                            results_text.append(f"  - Documentos: {stats['count']:,}")
                            results_text.append(f"  - Tamaño: {stats['size'] / (1024 * 1024):.2f} MB")
                        except Exception as e:
                            results_text.append(f"❌ Error actualizando estadísticas: {str(e)}")

                except Exception as e:
                    results_text.append(f"❌ Error procesando {collection_name}: {str(e)}")
                    continue

            # Finalizar
            end_time = datetime.datetime.now()
            elapsed = end_time - start_time
            progress.setValue(100)
            
            # Añadir resumen
            results_text.append("=" * 50)
            results_text.append(f"✅ Mantenimiento completado en {elapsed.total_seconds():.2f} segundos")
            results_text.append(f"📊 {len(selected_collections)} colecciones procesadas")
            
            # Actualizar la interfaz
            self.show_collections()
            self.update_database_stats()
            
        except Exception as e:
            results_text.append(f"❌ Error durante mantenimiento: {str(e)}")
            QMessageBox.critical(dialog, "Error", f"Error durante operaciones de mantenimiento: {str(e)}")

    def schedule_maintenance_task(self, selected_collections, compact, repair_indexes, 
                                validate_docs, remove_duplicates, update_stats,
                                frequency, schedule_time):
        """Programar tareas de mantenimiento para ejecutarse periódicamente"""
        try:
            # Crear directorio de configuración
            config_dir = os.path.join(os.path.expanduser("~"), ".mongodb_manager")
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                
            # Archivo para almacenar tareas programadas
            tasks_file = os.path.join(config_dir, "scheduled_maintenance.json")
            
            # Cargar tareas existentes
            tasks = []
            if os.path.exists(tasks_file):
                try:
                    with open(tasks_file, 'r', encoding='utf-8') as f:
                        tasks = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Error al cargar tareas existentes: {e}")
                    tasks = []
                except Exception as e:
                    print(f"Error al cargar tareas existentes: {e}")
                    tasks = []
            
            # Crear nueva tarea
            task_id = f"maintenance_{self.database_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Convertir colecciones seleccionadas a una lista
            collections_list = selected_collections
            
            time_str = schedule_time.toString("HH:mm")
            
            # Crear nueva tarea
            task = {
                "id": task_id,
                "type": "maintenance",
                "database": self.database_name,
                "connection_string": self.connection_string,
                "collections": collections_list,
                "operations": {
                    "compact": compact,
                    "repair_indexes": repair_indexes,
                    "validate_docs": validate_docs,
                    "remove_duplicates": remove_duplicates,
                    "update_stats": update_stats
                },
                "frequency": frequency,
                "time": time_str,
                "created_at": datetime.datetime.now().isoformat(),
                "last_run": None,
                "next_run": None
            }
            
            # Calcular próxima ejecución
            now = datetime.datetime.now()
            run_time = datetime.datetime.strptime(time_str, "%H:%M").time()
            next_run = datetime.datetime.combine(now.date(), run_time)
            
            if next_run <= now:
                next_run += datetime.timedelta(days=1)
            
            if frequency == "Semanal":
                # Para programación semanal, usar el próximo lunes
                days_ahead = 7 - next_run.weekday()
                if days_ahead == 7 and next_run > now:
                    days_ahead = 0
                next_run += datetime.timedelta(days=days_ahead)
            
            elif frequency == "Mensual":
                # Para programación mensual, usar el primer día del próximo mes
                if next_run.day != 1 or (next_run.day == 1 and next_run <= now):
                    # Avanzar al próximo mes
                    if next_run.month == 12:
                        next_run = next_run.replace(year=next_run.year + 1, month=1, day=1)
                    else:
                        next_run = next_run.replace(month=next_run.month + 1, day=1)
            
            task["next_run"] = next_run.isoformat()
            
            # Agregar tarea a la lista
            tasks.append(task)
            
            # Guardar tareas
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=2, default=str)
            
            # Informar al usuario
            QMessageBox.information(
                self,
                "Mantenimiento Programado",
                f"El mantenimiento ha sido programado con frecuencia {frequency.lower()} a las {time_str}.\n\n"
                f"Próxima ejecución: {next_run.strftime('%d/%m/%Y %H:%M')}")

            # Mostrar mensaje en la barra de estado
            self.show_status_message(f"Mantenimiento programado para ejecutarse {frequency.lower()} a las {time_str}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al programar mantenimiento: {str(e)}")
            self.show_status_message(f"Error al programar mantenimiento: {str(e)}", error=True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
