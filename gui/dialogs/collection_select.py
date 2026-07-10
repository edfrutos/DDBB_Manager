from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QListWidget, QDialogButtonBox
)


class CollectionSelectDialog(QDialog):
    """Diálogo genérico para seleccionar una colección de una lista."""

    def __init__(self, parent=None, collections=None, label=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Colección")
        self.resize(300, 200)

        layout = QVBoxLayout(self)

        text = label or "Seleccione una colección:"
        layout.addWidget(QLabel(text, self))

        self.collection_list = QListWidget(self)
        if collections:
            self.collection_list.addItems(collections)
        layout.addWidget(self.collection_list)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selected_collection(self):
        item = self.collection_list.currentItem()
        return item.text() if item else None
