import datetime

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ..dialogs import CollectionSelectDialog, CreateCollectionDialog, DropCollectionDialog


class DatabaseManagementMixin:
    """Métodos de gestión de bases de datos para MainWindow."""

    def create_collection(self):
        """Crear una nueva colección en la base de datos."""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        self.record_activity("create_collection")

        dialog = CreateCollectionDialog(self)
        if dialog.exec():
            collection_name = dialog.name_input.text().strip()

            if not collection_name:
                QMessageBox.warning(self, "Advertencia", "El nombre de la colección no puede estar vacío")
                return

            try:
                self.db.create_collection(collection_name)
                self.show_collections()
                self.update_database_stats()
                self.show_status_message(f"Collection '{collection_name}' created successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create collection: {str(e)}")
                self.show_status_message(f"Error: {str(e)}", error=True)

    def drop_collection(self):
        """Drop a collection from the database."""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        self.record_activity("drop_collection")

        try:
            collections = self.db.list_collection_names()

            if not collections:
                QMessageBox.information(self, "Información", "No hay colecciones para eliminar")
                return

            dialog = DropCollectionDialog(self, collections)
            if dialog.exec():
                collection_name = dialog.get_selected_collection()

                confirm = QMessageBox.question(
                    self,
                    "Confirmar Eliminación",
                    f"¿Está seguro de que desea eliminar la colección '{collection_name}'?\n¡Esta acción no se puede deshacer!",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if confirm == QMessageBox.StandardButton.Yes:
                    try:
                        self.db.drop_collection(collection_name)
                        self.show_collections()
                        self.update_database_stats()
                        self.show_status_message(f"Collection '{collection_name}' dropped successfully")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to drop collection: {str(e)}")
                        self.show_status_message(f"Error: {str(e)}", error=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process collection drop: {str(e)}")

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

    def get_all_collection_owners(self):
        """Get owner information for all collections in the database."""
        owners_cache = {}

        try:
            if not self.db:
                return {}

            collections = self.db.list_collection_names()
            for collection_name in collections:
                owners_cache[collection_name] = self.find_collection_owner(collection_name)

            return owners_cache
        except Exception as e:
            print(f"Error getting all collection owners: {e}")
            return {}

    def find_collection_owner(self, collection_name):
        """Encuentra el propietario de una colección buscando en metadatos y documentos."""
        owner_info = {
            "nombre": "Desconocido",
            "email": "N/A",
            "departamento": "N/A",
            "cargo": "N/A",
            "telefono": "N/A",
        }

        try:
            collection = self.db[collection_name]

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

                if owner_info["nombre"] != "Desconocido":
                    return owner_info

            owner_doc = (
                collection.find_one({"owner": {"$exists": True}})
                or collection.find_one({"created_by": {"$exists": True}})
                or collection.find_one({"creator": {"$exists": True}})
            )

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

        self.record_activity("switch_database")

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

        self.record_activity("show_global_stats")

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
