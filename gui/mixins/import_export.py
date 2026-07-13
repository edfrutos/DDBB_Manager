import csv
import json

from PyQt6.QtWidgets import QFileDialog, QMessageBox

try:
    from bson.objectid import ObjectId
except ImportError:
    ObjectId = None

from ..dialogs import ImportDialog, ExportDialog


class ImportExportMixin:
    """Métodos de importación y exportación de datos para MainWindow."""

    def import_data(self):
        """Import data from JSON or CSV file into a collection"""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        self.record_activity("import_data")

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

        self.record_activity("export_data")

        from PyQt6.QtWidgets import QFileDialog

        # Select collection to export
        collections = self.db.list_collection_names()

        if not collections:
            QMessageBox.information(self, "Información", "No hay colecciones para exportar")
            return

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
