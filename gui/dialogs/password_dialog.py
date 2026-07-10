from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QFrame
)


class PasswordManageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestión de Contraseñas")
        self.resize(400, 180)

        layout = QVBoxLayout(self)

        search_layout = QFormLayout()
        self.search_type = QComboBox(self)
        self.search_type.addItems(["Por ID", "Por Nombre", "Por Email"])
        search_layout.addRow("Buscar usuario:", self.search_type)

        self.search_text = QLineEdit(self)
        search_layout.addRow("Texto de búsqueda:", self.search_text)

        self.search_button = QPushButton("Buscar Usuario", self)
        self.search_button.setStyleSheet("background-color: #3498db; color: white;")

        layout.addLayout(search_layout)
        layout.addWidget(self.search_button)

        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self.user_label = QLabel("Seleccione un usuario primero", self)
        layout.addWidget(self.user_label)

        password_layout = QFormLayout()
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setEnabled(False)
        password_layout.addRow("Nueva Contraseña:", self.password_input)

        self.confirm_input = QLineEdit(self)
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setEnabled(False)
        password_layout.addRow("Confirmar Contraseña:", self.confirm_input)
        layout.addLayout(password_layout)

        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Cambiar Contraseña", self)
        self.save_button.setStyleSheet("background-color: #2ecc71; color: white;")
        self.save_button.setEnabled(False)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancelar", self)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.selected_user = None
        self.selected_collection = None
