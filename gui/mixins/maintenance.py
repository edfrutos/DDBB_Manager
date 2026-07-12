import os
import json
import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QGroupBox, QTextEdit, QProgressDialog,
    QWidget, QTimeEdit, QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QTime

try:
    from bson.objectid import ObjectId
except ImportError:
    ObjectId = None


class MaintenanceMixin:
    """Métodos de mantenimiento de colecciones para MainWindow."""

    def maintain_collections(self):
        """Realizar tareas de mantenimiento en colecciones"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        try:
            collections = self.db.list_collection_names()

            if not collections:
                QMessageBox.information(self, "Información", "No hay colecciones disponibles para mantenimiento")
                return

            maintenance_dialog = QDialog(self)
            maintenance_dialog.setWindowTitle("Mantenimiento de Colecciones")
            maintenance_dialog.resize(700, 550)

            layout = QVBoxLayout(maintenance_dialog)

            title_label = QLabel("<h2>Mantenimiento de Colecciones</h2>")
            title_label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(title_label)

            info_label = QLabel("Seleccione las colecciones a mantener y las operaciones de mantenimiento a realizar.")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)

            collections_group = QGroupBox("Seleccionar Colecciones")
            collections_layout = QVBoxLayout(collections_group)

            collections_list = QListWidget()
            collections_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            for collection in collections:
                collections_list.addItem(QListWidgetItem(collection))
            collections_layout.addWidget(collections_list)

            selection_buttons = QHBoxLayout()
            select_all_button = QPushButton("Seleccionar Todos")
            select_all_button.clicked.connect(lambda: self.select_all_items(collections_list, True))
            selection_buttons.addWidget(select_all_button)

            clear_selection_button = QPushButton("Limpiar Selección")
            clear_selection_button.clicked.connect(lambda: self.select_all_items(collections_list, False))
            selection_buttons.addWidget(clear_selection_button)
            collections_layout.addLayout(selection_buttons)
            layout.addWidget(collections_group)

            maintenance_group = QGroupBox("Operaciones de Mantenimiento")
            maintenance_layout = QVBoxLayout(maintenance_group)
            compact_check = QCheckBox("Compactar colecciones (reduce fragmentación)")
            maintenance_layout.addWidget(compact_check)
            repair_indexes_check = QCheckBox("Reparar índices (reconstruye índices dañados)")
            maintenance_layout.addWidget(repair_indexes_check)
            validate_docs_check = QCheckBox("Validar integridad de documentos")
            maintenance_layout.addWidget(validate_docs_check)
            remove_duplicates_check = QCheckBox("Eliminar documentos duplicados")
            maintenance_layout.addWidget(remove_duplicates_check)
            update_stats_check = QCheckBox("Actualizar estadísticas")
            update_stats_check.setChecked(True)
            maintenance_layout.addWidget(update_stats_check)
            layout.addWidget(maintenance_group)

            advanced_group = QGroupBox("Opciones Avanzadas")
            advanced_layout = QVBoxLayout(advanced_group)
            schedule_check = QCheckBox("Programar mantenimiento periódico")
            advanced_layout.addWidget(schedule_check)

            schedule_options = QWidget()
            schedule_options.setEnabled(False)
            schedule_options_layout = QFormLayout(schedule_options)
            frequency_combo = QComboBox()
            frequency_combo.addItems(["Diario", "Semanal", "Mensual"])
            schedule_options_layout.addRow("Frecuencia:", frequency_combo)
            time_edit = QTimeEdit()
            time_edit.setTime(QTime(3, 0))
            schedule_options_layout.addRow("Hora:", time_edit)
            advanced_layout.addWidget(schedule_options)
            schedule_check.toggled.connect(schedule_options.setEnabled)
            layout.addWidget(advanced_group)

            results_group = QGroupBox("Resultados de Mantenimiento")
            results_layout = QVBoxLayout(results_group)
            results_text = QTextEdit()
            results_text.setReadOnly(True)
            results_text.setPlaceholderText("Los resultados de las operaciones de mantenimiento se mostrarán aquí.")
            results_layout.addWidget(results_text)
            layout.addWidget(results_group)

            button_layout = QHBoxLayout()
            execute_button = QPushButton("Ejecutar Mantenimiento")
            execute_button.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
            button_layout.addWidget(execute_button)
            close_button = QPushButton("Cerrar")
            button_layout.addWidget(close_button)
            layout.addLayout(button_layout)

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
                maintenance_dialog,
            ))
            close_button.clicked.connect(maintenance_dialog.reject)

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
            if schedule_maintenance:
                self.schedule_maintenance_task(
                    selected_collections, compact, repair_indexes,
                    validate_docs, remove_duplicates, update_stats,
                    frequency, schedule_time,
                )
                results_text.append("✅ Programación de mantenimiento configurada correctamente.")
                results_text.append(f"📅 Frecuencia: {frequency}")
                results_text.append(f"🕒 Hora: {schedule_time.toString('HH:mm')}")
                return

            progress = QProgressDialog("Iniciando operaciones de mantenimiento...", "Cancelar", 0, 100, dialog)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setValue(0)
            progress.show()

            start_time = datetime.datetime.now()
            results_text.clear()
            results_text.append(f"🚀 Iniciando mantenimiento: {start_time.strftime('%d/%m/%Y %H:%M:%S')}")
            results_text.append(f"📊 Colecciones seleccionadas: {len(selected_collections)}")

            collections = self.db.list_collection_names()
            if not collections:
                QMessageBox.warning(dialog, "Advertencia", "No hay colecciones disponibles para mantenimiento")
                return

            for i, collection_name in enumerate(selected_collections, 1):
                if progress.wasCanceled():
                    break
                try:
                    collection = self.db[collection_name]
                    progress.setValue(int(i / len(selected_collections) * 100))
                    progress.setLabelText(f"Procesando {collection_name} ({i}/{len(selected_collections)})...")

                    if compact:
                        results_text.append(f"\nCompactando {collection_name}...")
                        try:
                            result = collection.compact()
                            results_text.append(f"✅ Compactación completada: {result}")
                        except Exception as e:
                            results_text.append(f"❌ Error compactando {collection_name}: {str(e)}")

                    if repair_indexes:
                        results_text.append(f"\nReparando índices de {collection_name}...")
                        try:
                            indexes = collection.list_indexes()
                            for index in indexes:
                                if index["name"] != "_id_":
                                    collection.drop_index(index["name"])
                                    collection.create_index(index["key"], name=index["name"])
                            results_text.append("✅ Índices reparados")
                        except Exception as e:
                            results_text.append(f"❌ Error reparando índices: {str(e)}")

                    if validate_docs:
                        results_text.append(f"\nValidando documentos de {collection_name}...")
                        try:
                            validation = collection.validate()
                            results_text.append(f"✅ Validación completada: {validation['valid']}")
                            if not validation['valid']:
                                results_text.append(f"⚠️ Errores encontrados: {validation['errors']}")
                        except Exception as e:
                            results_text.append(f"❌ Error validando documentos: {str(e)}")

                    if remove_duplicates:
                        results_text.append(f"\nEliminando duplicados de {collection_name}...")
                        try:
                            seen = set()
                            duplicates = []
                            for doc in collection.find():
                                doc_id = str(doc['_id'])
                                if doc_id in seen:
                                    duplicates.append(doc_id)
                                seen.add(doc_id)
                            if duplicates and ObjectId is not None:
                                for doc_id in duplicates:
                                    collection.delete_one({'_id': ObjectId(doc_id)})
                                results_text.append(f"✅ Eliminados {len(duplicates)} duplicados")
                            else:
                                results_text.append("✅ No se encontraron duplicados")
                        except Exception as e:
                            results_text.append(f"❌ Error eliminando duplicados: {str(e)}")

                    if update_stats:
                        results_text.append(f"\nActualizando estadísticas de {collection_name}...")
                        try:
                            stats = collection.stats()
                            results_text.append("✅ Estadísticas actualizadas")
                            results_text.append(f"  - Documentos: {stats['count']:,}")
                            results_text.append(f"  - Tamaño: {stats['size'] / (1024 * 1024):.2f} MB")
                        except Exception as e:
                            results_text.append(f"❌ Error actualizando estadísticas: {str(e)}")

                except Exception as e:
                    results_text.append(f"❌ Error procesando {collection_name}: {str(e)}")
                    continue

            end_time = datetime.datetime.now()
            elapsed = end_time - start_time
            progress.setValue(100)
            results_text.append("=" * 50)
            results_text.append(f"✅ Mantenimiento completado en {elapsed.total_seconds():.2f} segundos")
            results_text.append(f"📊 {len(selected_collections)} colecciones procesadas")

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
            config_dir = os.path.join(os.path.expanduser("~"), ".mongodb_manager")
            os.makedirs(config_dir, exist_ok=True)

            tasks_file = os.path.join(config_dir, "scheduled_maintenance.json")
            tasks = []
            if os.path.exists(tasks_file):
                try:
                    with open(tasks_file, 'r', encoding='utf-8') as f:
                        tasks = json.load(f)
                except (json.JSONDecodeError, Exception):
                    tasks = []

            task_id = f"maintenance_{self.database_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            time_str = schedule_time.toString("HH:mm")

            task = {
                "id": task_id,
                "type": "maintenance",
                "database": self.database_name,
                "connection_string": self.connection_string,
                "collections": selected_collections,
                "operations": {
                    "compact": compact,
                    "repair_indexes": repair_indexes,
                    "validate_docs": validate_docs,
                    "remove_duplicates": remove_duplicates,
                    "update_stats": update_stats,
                },
                "frequency": frequency,
                "time": time_str,
                "created_at": datetime.datetime.now().isoformat(),
                "last_run": None,
                "next_run": None,
            }

            now = datetime.datetime.now()
            run_time = datetime.datetime.strptime(time_str, "%H:%M").time()
            next_run = datetime.datetime.combine(now.date(), run_time)

            if next_run <= now:
                next_run += datetime.timedelta(days=1)

            if frequency == "Semanal":
                days_ahead = 7 - next_run.weekday()
                if days_ahead == 7 and next_run > now:
                    days_ahead = 0
                next_run += datetime.timedelta(days=days_ahead)
            elif frequency == "Mensual":
                if next_run.day != 1 or (next_run.day == 1 and next_run <= now):
                    if next_run.month == 12:
                        next_run = next_run.replace(year=next_run.year + 1, month=1, day=1)
                    else:
                        next_run = next_run.replace(month=next_run.month + 1, day=1)

            task["next_run"] = next_run.isoformat()
            tasks.append(task)

            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=2, default=str)

            QMessageBox.information(
                self,
                "Mantenimiento Programado",
                f"El mantenimiento ha sido programado con frecuencia {frequency.lower()} a las {time_str}.\n\n"
                f"Próxima ejecución: {next_run.strftime('%d/%m/%Y %H:%M')}",
            )
            self.show_status_message(f"Mantenimiento programado para ejecutarse {frequency.lower()} a las {time_str}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al programar mantenimiento: {str(e)}")
            self.show_status_message(f"Error al programar mantenimiento: {str(e)}", error=True)
