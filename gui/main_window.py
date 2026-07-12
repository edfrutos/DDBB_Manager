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
    QTimeEdit, QScrollArea, QLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QTimer, QTime, QDateTime, QDate
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont, QIcon, QAction
from .dialogs import (
    CreateCollectionDialog,
    DropCollectionDialog,
    ImportDialog,
    ExportDialog,
    PasswordManageDialog,
)
from .mixins import (
    MaintenanceMixin,
    BackupMixin,
    UserManagementMixin,
    ImportExportMixin,
    DatabaseManagementMixin,
    IndexManagementMixin,
    HelpMixin,
    CollectionViewMixin,
)

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
class MainWindow(
    MaintenanceMixin,
    BackupMixin,
    UserManagementMixin,
    ImportExportMixin,
    DatabaseManagementMixin,
    IndexManagementMixin,
    HelpMixin,
    CollectionViewMixin,
    QMainWindow,
):
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
        return super().show_collections()

    def create_flat_view(self, model, collections):
        return super().create_flat_view(model, collections)

    def create_type_grouped_view(self, model, collections):
        return super().create_type_grouped_view(model, collections)

    def create_user_grouped_view(self, model, collections):
        return super().create_user_grouped_view(model, collections)

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
        return super().reset_and_show_collections()

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
        return super().is_tree_view_valid()

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
        return super().ensure_tree_view_exists()

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
        return super().view_collection_data(index)

    def show_collection_data(self, collection_name, limit=100, with_metadata=False):
        return super().show_collection_data(collection_name, limit=limit, with_metadata=with_metadata)

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
