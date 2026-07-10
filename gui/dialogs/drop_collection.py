from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox
)


class DropCollectionDialog(QDialog):
    def __init__(self, parent=None, collections=None):
        super().__init__(parent)
        self.setWindowTitle("Eliminar Colección")
        self.resize(300, 120)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Seleccione colección a eliminar:"))

        self.collection_combo = QComboBox(self)
        if collections:
            self.collection_combo.addItems(collections)
        layout.addWidget(self.collection_combo)

        warning = QLabel("¡ADVERTENCIA: Esta acción no se puede deshacer!")
        warning.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(warning)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selected_collection(self):
        return self.collection_combo.currentText()
