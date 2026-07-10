from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox
)


class ExportDialog(QDialog):
    def __init__(self, parent=None, collections=None):
        super().__init__(parent)
        self.setWindowTitle("Exportar Colección")
        self.resize(400, 150)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Seleccionar colección a exportar:"))
        self.collection_combo = QComboBox(self)
        if collections:
            self.collection_combo.addItems(collections)
        layout.addWidget(self.collection_combo)

        layout.addWidget(QLabel("Seleccionar formato de exportación:"))
        self.format_combo = QComboBox(self)
        self.format_combo.addItems(["JSON", "CSV"])
        layout.addWidget(self.format_combo)

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
