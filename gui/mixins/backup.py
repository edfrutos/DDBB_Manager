import os
import json
import datetime
import gzip
import threading

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QCheckBox, QGroupBox, QProgressDialog, QFileDialog,
    QRadioButton, QButtonGroup, QComboBox, QTimeEdit, QSpinBox,
    QDialogButtonBox, QMessageBox, QApplication, QWidget,
)
from PyQt6.QtCore import Qt, QTime

try:
    from bson.objectid import ObjectId
except ImportError:
    ObjectId = None


class BackupMixin:
    """Métodos de respaldo y restauración de la base de datos para MainWindow."""

    def backup_database(self):
        """Crear un respaldo de la base de datos"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        try:
            collections = self.db.list_collection_names()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al obtener colecciones: {str(e)}")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Respaldo de Base de Datos")
        dialog.resize(650, 600)

        layout = QVBoxLayout(dialog)

        title_label = QLabel("<h2>Respaldo de Base de Datos</h2>")
        title_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(title_label)

        path_group = QGroupBox("Ruta de Respaldo")
        path_layout = QHBoxLayout(path_group)
        default_path = os.path.join(
            os.path.expanduser("~"), "MongoDB_Backups",
            f"{self.database_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        path_edit = QLineEdit(default_path)
        path_layout.addWidget(path_edit)
        browse_button = QPushButton("Examinar...")

        def browse_path():
            selected = QFileDialog.getExistingDirectory(
                dialog, "Seleccionar Directorio de Respaldo", os.path.expanduser("~")
            )
            if selected:
                path_edit.setText(selected)

        browse_button.clicked.connect(browse_path)
        path_layout.addWidget(browse_button)
        layout.addWidget(path_group)

        type_group = QGroupBox("Tipo de Respaldo")
        type_layout = QVBoxLayout(type_group)
        type_button_group = QButtonGroup(dialog)
        full_radio = QRadioButton("Respaldo Completo (todas las colecciones)")
        full_radio.setChecked(True)
        type_button_group.addButton(full_radio)
        type_layout.addWidget(full_radio)
        selective_radio = QRadioButton("Respaldo Selectivo (colecciones específicas)")
        type_button_group.addButton(selective_radio)
        type_layout.addWidget(selective_radio)

        collections_list = QListWidget()
        collections_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for collection in collections:
            collections_list.addItem(QListWidgetItem(collection))
        collections_list.setEnabled(False)
        type_layout.addWidget(collections_list)
        selective_radio.toggled.connect(collections_list.setEnabled)
        layout.addWidget(type_group)

        compress_group = QGroupBox("Compresión")
        compress_layout = QFormLayout(compress_group)
        compress_check = QCheckBox("Comprimir respaldo (gzip)")
        compress_check.setChecked(True)
        compress_layout.addRow(compress_check)
        compression_level_spin = QSpinBox()
        compression_level_spin.setRange(1, 9)
        compression_level_spin.setValue(6)
        compress_layout.addRow("Nivel de compresión:", compression_level_spin)
        compress_check.toggled.connect(compression_level_spin.setEnabled)
        layout.addWidget(compress_group)

        schedule_group = QGroupBox("Opciones Avanzadas")
        schedule_layout = QVBoxLayout(schedule_group)
        schedule_check = QCheckBox("Programar respaldo periódico")
        schedule_layout.addWidget(schedule_check)

        schedule_options = QWidget()
        schedule_options.setEnabled(False)
        schedule_options_layout = QFormLayout(schedule_options)
        frequency_combo = QComboBox()
        frequency_combo.addItems(["Diario", "Semanal", "Mensual"])
        schedule_options_layout.addRow("Frecuencia:", frequency_combo)
        day_combo = QComboBox()
        day_combo.addItems(["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])
        schedule_options_layout.addRow("Día de la semana:", day_combo)
        time_edit = QTimeEdit()
        time_edit.setTime(QTime(3, 0))
        schedule_options_layout.addRow("Hora:", time_edit)
        schedule_layout.addWidget(schedule_options)
        schedule_check.toggled.connect(schedule_options.setEnabled)
        layout.addWidget(schedule_group)

        button_box = QDialogButtonBox()
        execute_button = QPushButton("Ejecutar Respaldo")
        execute_button.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        button_box.addButton(execute_button, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = QPushButton("Cancelar")
        button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(button_box)

        execute_button.clicked.connect(lambda: self.execute_backup(
            path_edit.text().strip(),
            full_radio.isChecked(),
            [collections_list.item(i).text() for i in range(collections_list.count())
             if collections_list.item(i).isSelected()],
            compress_check.isChecked(),
            compression_level_spin.value(),
            schedule_check.isChecked(),
            frequency_combo.currentText(),
            time_edit.time(),
            day_combo.currentText(),
            dialog,
        ))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def execute_backup(self, backup_path, is_full_backup, selected_collections, compress_backup,
                       compression_level, schedule_backup, schedule_frequency, schedule_time,
                       schedule_day, dialog):
        """Ejecutar el respaldo con las opciones configuradas"""
        try:
            if not backup_path:
                QMessageBox.warning(dialog, "Advertencia", "Por favor, especifique una ruta de respaldo válida")
                return

            if not is_full_backup and not selected_collections:
                QMessageBox.warning(dialog, "Advertencia", "Por favor, seleccione al menos una colección para el respaldo selectivo")
                return

            if not os.path.exists(backup_path):
                os.makedirs(backup_path)

            if schedule_backup:
                self.schedule_backup_task(backup_path, is_full_backup, selected_collections,
                                        compress_backup, compression_level,
                                        schedule_frequency, schedule_time, schedule_day)
                dialog.accept()
                return

            progress_dialog = QProgressDialog("Preparando respaldo...", "Cancelar", 0, 100, dialog)
            progress_dialog.setWindowTitle("Respaldo en progreso")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setAutoClose(False)
            progress_dialog.setAutoReset(False)
            progress_dialog.setValue(0)
            progress_dialog.show()

            def perform_backup():
                try:
                    progress_dialog.setLabelText("Recopilando información de la base de datos...")
                    progress_dialog.setValue(5)

                    collections_to_backup = []
                    if is_full_backup:
                        collections_to_backup = [col for col in self.db.list_collection_names()
                                               if not col.startswith('system.')]
                    else:
                        collections_to_backup = selected_collections

                    progress_dialog.setLabelText(f"Respaldando {len(collections_to_backup)} colecciones...")
                    progress_dialog.setValue(10)

                    metadata = {
                        'database': self.database_name,
                        'timestamp': datetime.datetime.now().isoformat(),
                        'collections': collections_to_backup,
                        'compressed': compress_backup,
                        'full_backup': is_full_backup,
                        'version': '1.0'
                    }

                    metadata_path = os.path.join(backup_path, 'metadata.json')
                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, default=str)

                    data_dir = os.path.join(backup_path, 'collections')
                    if not os.path.exists(data_dir):
                        os.makedirs(data_dir)

                    total_collections = len(collections_to_backup)
                    for i, collection_name in enumerate(collections_to_backup):
                        if progress_dialog.wasCanceled():
                            break

                        progress_percent = 10 + int((i / total_collections) * 80)
                        progress_dialog.setValue(progress_percent)
                        progress_dialog.setLabelText(f"Respaldando colección: {collection_name}...")

                        try:
                            collection = self.db[collection_name]
                            documents = list(collection.find())

                            collection_file = os.path.join(data_dir, f"{collection_name}.json")

                            if compress_backup:
                                with gzip.open(collection_file + '.gz', 'wt', encoding='utf-8', compresslevel=compression_level) as f:
                                    json.dump(documents, f, default=str, indent=None)
                            else:
                                with open(collection_file, 'w', encoding='utf-8') as f:
                                    json.dump(documents, f, default=str, indent=2)

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

                    log_file = os.path.join(backup_path, 'backup_log.txt')
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write(f"Respaldo de {self.database_name} completado en {datetime.datetime.now().isoformat()}\n")
                        f.write(f"Tipo: {'Completo' if is_full_backup else 'Selectivo'}\n")
                        f.write(f"Colecciones respaldadas: {len(collections_to_backup)}\n")
                        for col in collections_to_backup:
                            f.write(f"  - {col}\n")

                    progress_dialog.setValue(100)
                    progress_dialog.setLabelText("Respaldo completado con éxito")

                    return True, "Respaldo completado con éxito"

                except Exception as e:
                    progress_dialog.setLabelText(f"Error durante el respaldo: {str(e)}")
                    print(f"Error durante el respaldo: {e}")
                    return False, str(e)

            backup_thread = threading.Thread(target=perform_backup)
            backup_thread.daemon = True
            backup_thread.start()

            while backup_thread.is_alive() and not progress_dialog.wasCanceled():
                QApplication.processEvents()

            if progress_dialog.wasCanceled():
                QMessageBox.warning(dialog, "Advertencia", "Respaldo cancelado por el usuario")
                dialog.accept()
                return

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
            config_dir = os.path.join(os.path.expanduser("~"), ".mongodb_manager")
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)

            tasks_file = os.path.join(config_dir, "scheduled_backups.json")

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

            task_id = f"backup_{self.database_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

            collections_list = selected_collections

            time_str = schedule_time.toString("HH:mm")

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

            now = datetime.datetime.now()
            run_time = datetime.datetime.strptime(time_str, "%H:%M").time()
            next_run = datetime.datetime.combine(now.date(), run_time)

            if next_run <= now:
                next_run += datetime.timedelta(days=1)

            if frequency == "Semanal":
                days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                target_day = days.index(day_of_week)
                current_day = next_run.weekday()

                days_until_target = (target_day - current_day) % 7
                if days_until_target == 0 and next_run <= now:
                    days_until_target = 7

                next_run += datetime.timedelta(days=days_until_target)
            elif frequency == "Mensual":
                next_month = next_run.replace(day=1) + datetime.timedelta(days=32)
                next_run = next_month.replace(day=1)

            task["next_run"] = next_run.isoformat()

            tasks.append(task)

            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=2, default=str)

            QMessageBox.information(
                self,
                "Respaldo Programado",
                f"El respaldo ha sido programado con frecuencia {frequency.lower()} a las {time_str}.\n\n"
                f"Próxima ejecución: {next_run.strftime('%d/%m/%Y %H:%M')}")

            self.show_status_message("Respaldo programado correctamente")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al programar el respaldo: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)

    def restore_database(self):
        """Restaurar la base de datos desde un respaldo"""
        if self.db is None:
            QMessageBox.critical(self, "Error", "No hay conexión a la base de datos")
            return

        backup_dir = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Directorio de Respaldo",
            os.path.join(os.path.expanduser("~"), "MongoDB_Backups")
        )
        if not backup_dir:
            return

        metadata_path = os.path.join(backup_dir, 'metadata.json')
        if not os.path.exists(metadata_path):
            QMessageBox.warning(self, "Advertencia", "El directorio seleccionado no contiene un respaldo válido (falta archivo metadata.json)")
            return

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

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

            available_collections = metadata.get('collections', [])
            is_compressed = metadata.get('compressed', False)

            if not available_collections:
                QMessageBox.warning(self, "Advertencia", "El respaldo no contiene colecciones para restaurar")
                return

            restore_dialog = QDialog(self)
            restore_dialog.setWindowTitle("Restaurar Base de Datos desde Respaldo")
            restore_dialog.resize(600, 500)

            layout = QVBoxLayout(restore_dialog)

            timestamp = metadata.get('timestamp', 'Desconocido')
            if isinstance(timestamp, str) and len(timestamp) > 19:
                timestamp = timestamp[:19].replace("T", " ")

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

            options_group = QGroupBox("Opciones de Restauración")
            options_layout = QVBoxLayout(options_group)

            restore_type_group = QButtonGroup(restore_dialog)

            full_restore_radio = QRadioButton("Restauración Completa (todas las colecciones del respaldo)")
            full_restore_radio.setChecked(True)
            restore_type_group.addButton(full_restore_radio)
            options_layout.addWidget(full_restore_radio)

            selective_restore_radio = QRadioButton("Restauración Selectiva (colecciones específicas)")
            restore_type_group.addButton(selective_restore_radio)
            options_layout.addWidget(selective_restore_radio)

            layout.addWidget(options_group)

            collections_group = QGroupBox("Seleccionar Colecciones")
            collections_layout = QVBoxLayout(collections_group)

            collections_list = QListWidget()
            collections_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

            for collection in available_collections:
                item = QListWidgetItem(collection)
                item.setSelected(True)
                collections_list.addItem(item)

            collections_layout.addWidget(collections_list)
            collections_group.setEnabled(False)
            layout.addWidget(collections_group)

            selective_restore_radio.toggled.connect(collections_group.setEnabled)

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

            button_box = QDialogButtonBox()

            restore_button = QPushButton("Iniciar Restauración")
            restore_button.setStyleSheet("background-color: #2ecc71; color: white;")
            button_box.addButton(restore_button, QDialogButtonBox.ButtonRole.AcceptRole)

            cancel_button = QPushButton("Cancelar")
            button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)

            layout.addWidget(button_box)

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

            restore_dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al procesar el respaldo: {str(e)}")
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

                        for doc in documents:
                            if (
                                ObjectId is not None
                                and "_id" in doc
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
