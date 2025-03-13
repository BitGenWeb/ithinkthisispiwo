import logging

import requests
from PySide6.QtWidgets import (QDialog, QLineEdit, QCheckBox, QVBoxLayout, QLabel, QMessageBox,
                               QPushButton, QWidget, QHBoxLayout)
from .constants import MODRINTH_STYLE, SERVER_URL
from .register_dialog import RegisterDialog

logger = logging.getLogger(__name__)

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Инициализация диалога авторизации")
        self.setWindowTitle("Авторизация")
        self.setFixedSize(300, 250)
        self.setStyleSheet(MODRINTH_STYLE)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Введите ваш логин")
        layout.addWidget(QLabel("Логин:"))
        layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Введите ваш пароль")
        layout.addWidget(QLabel("Пароль:"))
        layout.addWidget(self.password_input)

        self.remember_me_checkbox = QCheckBox("Запомнить меня")
        self.remember_me_checkbox.setChecked(True)
        layout.addWidget(self.remember_me_checkbox)

        self.offline_checkbox = QCheckBox("Оффлайн-режим")
        layout.addWidget(self.offline_checkbox)

        # Создаем контейнер для кнопок
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Настройки для всех кнопок
        button_style = """
            QPushButton {
                min-width: 70px;
                padding: 5px;
                margin: 2px;
            }
        """

        # Кнопка входа
        self.login_button = QPushButton("Войти")
        self.login_button.clicked.connect(self.accept_login)
        self.login_button.setStyleSheet(button_style)

        # Кнопка регистрации
        self.register_btn = QPushButton("Регистрация")
        self.register_btn.clicked.connect(self.show_register_dialog)
        self.register_btn.setStyleSheet(button_style)

        # Кнопка отмены
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet(button_style)

        # Распределение кнопок с растяжками
        button_layout.addWidget(self.login_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.register_btn)
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)

        layout.addWidget(button_container)

        self.activateWindow()


    def accept_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        offline_mode = self.offline_checkbox.isChecked()

        if not username:
            QMessageBox.critical(self, "Ошибка", "Никнейм обязателен для входа!")
            return

        if not offline_mode and not password:
            QMessageBox.critical(self, "Ошибка", "Пароль обязателен в онлайн-режиме!")
            return

        self.accept()

    def get_credentials(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        offline = self.offline_checkbox.isChecked()
        remember_me = self.remember_me_checkbox.isChecked()
        logger.info(f"Получены данные: username={username}, offline={offline}, remember_me={remember_me}")
        return username, password, offline, remember_me

    def show_register_dialog(self):
        dialog = RegisterDialog(self)
        if dialog.exec() == QDialog.Accepted:
            username, password = dialog.get_credentials()
            try:
                response = requests.post(f"{SERVER_URL}/api/register", json={
                    "username": username,
                    "password": password
                }, timeout=5)
                if response.status_code == 201:
                    QMessageBox.information(self, "Успех", "Аккаунт создан!")
                else:
                    QMessageBox.critical(self, "Ошибка", response.json().get("error"))
            except requests.RequestException:
                QMessageBox.critical(self, "Ошибка", "Сервер недоступен")