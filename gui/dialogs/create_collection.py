from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox


class CreateCollectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Colección")
        self.resize(300, 100)

        layout = QFormLayout(self)

        self.name_input = QLineEdit(self)
        layout.addRow("Nombre de la colección:", self.name_input)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)
