import logging
from PySide6.QtWidgets import QDialog, QLineEdit, QVBoxLayout, QLabel, QDialogButtonBox, QMessageBox

logger = logging.getLogger(__name__)


class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Регистрация")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Логин")
        layout.addWidget(QLabel("Логин:"))
        layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Пароль")
        layout.addWidget(QLabel("Пароль:"))
        layout.addWidget(self.password_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_input)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def validate_input(self):
        if not self.username_input.text().strip():
            QMessageBox.critical(self, "Ошибка", "Введите логин!")
            return
        if not self.password_input.text().strip():
            QMessageBox.critical(self, "Ошибка", "Введите пароль!")
            return
        self.accept()

    def get_credentials(self):
        return self.username_input.text().strip(), self.password_input.text().strip()