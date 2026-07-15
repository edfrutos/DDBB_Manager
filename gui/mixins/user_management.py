import hashlib
import datetime

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

try:
    from bson.objectid import ObjectId
except ImportError:
    ObjectId = None

from ..dialogs import PasswordManageDialog


class UserManagementMixin:
    """Métodos de gestión de usuarios para MainWindow."""

    def _normalize_user_id(self, user_id):
        """Return an ObjectId when possible, otherwise keep the original id."""
        if isinstance(user_id, str) and ObjectId is not None:
            try:
                return ObjectId(user_id)
            except Exception:
                return user_id
        return user_id

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

    def search_user(self):
        """Buscar usuarios por ID, nombre o email en la colección unificada."""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Buscar Usuario")
        dialog.resize(400, 150)

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        search_type = QComboBox()
        search_type.addItems(["Por ID", "Por Nombre", "Por Email"])
        form_layout.addRow("Buscar usuario:", search_type)

        search_text = QLineEdit()
        form_layout.addRow("Texto de búsqueda:", search_text)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        text = search_text.text().strip()
        if not text:
            QMessageBox.warning(self, "Advertencia", "Introduzca un texto de búsqueda")
            return

        collection_name = 'users_unified'

        try:
            if search_type.currentText() == "Por ID":
                query = {'_id': self._normalize_user_id(text)}
            elif search_type.currentText() == "Por Nombre":
                query = {'$or': [
                    {'nombre': {'$regex': text, '$options': 'i'}},
                    {'name': {'$regex': text, '$options': 'i'}}
                ]}
            else:  # Por Email
                query = {'email': {'$regex': text, '$options': 'i'}}

            users = list(self.db[collection_name].find(query))
            for user in users:
                user['_source_collection'] = collection_name

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al buscar el usuario: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            return

        if not users:
            QMessageBox.information(self, "Información", "No se encontraron usuarios que coincidan con los criterios")
            return

        self.show_user_results(users)

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

        self.record_activity("edit_user")

        try:
            # Si no se proporcionan user_id y collection_name, pedir al usuario que busque primero
            if user_id is None or collection_name is None:
                QMessageBox.information(self, "Información", "Utilice la función de búsqueda para encontrar un usuario a editar")
                self.search_user()
                return

            # Obtener documento del usuario
            user_id = self._normalize_user_id(user_id)

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

        self.record_activity("delete_user")

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
            user_id = self._normalize_user_id(user_id)

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

        self.record_activity("manage_password")

        try:
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
            self.record_activity("update_user_password")
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

    def search_user_for_password(self, dialog):
        """Buscar un usuario para asociarlo al diálogo de cambio de contraseña"""
        try:
            search_text = dialog.search_text.text().strip()
            if not search_text:
                QMessageBox.warning(self, "Advertencia", "Introduzca un texto de búsqueda")
                return

            collection_name = 'users_unified'
            found_users = []

            if dialog.search_type.currentText() == "Por ID":
                from bson.objectid import ObjectId
                try:
                    query = {'_id': ObjectId(search_text)}
                except Exception:
                    QMessageBox.warning(self, "Advertencia", "ID de usuario no válido")
                    return
            elif dialog.search_type.currentText() == "Por Nombre":
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
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al buscar el usuario: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
            return

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
