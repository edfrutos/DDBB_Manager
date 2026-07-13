from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..dialogs import CollectionSelectDialog


class IndexManagementMixin:
    """Métodos de gestión de índices para MainWindow."""

    def manage_indexes(self):
        """Crear y gestionar índices para colecciones en la base de datos"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        self.record_activity("manage_indexes")

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
