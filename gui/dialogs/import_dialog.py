from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QLineEdit, QDialogButtonBox
)


class ImportDialog(QDialog):
    def __init__(self, parent=None, collections=None):
        super().__init__(parent)
        self.setWindowTitle("Importar Datos")
        self.resize(400, 200)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Seleccione colección destino:"))
        self.collection_combo = QComboBox(self)
        if collections:
            self.collection_combo.addItems(collections)
        layout.addWidget(self.collection_combo)

        layout.addWidget(QLabel("O crear una nueva colección:"))
        self.new_collection_input = QLineEdit(self)
        layout.addWidget(self.new_collection_input)

        layout.addWidget(QLabel("Opciones de importación:"))
        self.clear_collection = QComboBox(self)
        self.clear_collection.addItems([
            "Añadir a documentos existentes",
            "Reemplazar contenido de la colección",
        ])
        layout.addWidget(self.clear_collection)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_target_collection(self):
        new_col = self.new_collection_input.text().strip()
        return new_col if new_col else self.collection_combo.currentText()

    def should_clear_collection(self):
        return self.clear_collection.currentIndex() == 1
