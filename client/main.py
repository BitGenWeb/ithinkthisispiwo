import sys
import argparse
import json
import os
import requests
import logging
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from .constants import BASE_DIR, SERVER_URL
from .launcher_window import LauncherWindow
from .login_dialog import LoginDialog

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding="UTF-8",
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "log.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Запуск приложения")
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", help="Логин пользователя")
    parser.add_argument("--password", help="Пароль пользователя")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    config_file = os.path.join(BASE_DIR, "launcher_config.json")
    saved_credentials = {}
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            saved_credentials = json.load(f)
            logger.info(f"Загружены сохранённые данные: {saved_credentials}")

    username = args.username or saved_credentials.get("username")
    password = args.password or saved_credentials.get("password")
    offline_mode = False
    server_builds = []
    license_expiry = None
    role = "Player"

    if username and password and not args.username and not args.password:
        logger.info(f"Попытка автовхода для {username}")
        try:
            response = requests.post(f"{SERVER_URL}/api/auth", json={
                "action": "login",
                "username": username,
                "password": password
            }, timeout=20)
            data = response.json()
            if response.status_code == 200 and data.get("status") == "success":
                server_builds = data.get("builds", [])
                license_expiry = data.get("license_expiry", "N/A")
                role = data.get("role", "Player")
                logger.info(f"Автовход успешен для {username}, сборки: {server_builds}, role: {role}")
                launcher = LauncherWindow(username, offline_mode, server_builds, license_expiry, role)
                launcher.show()
                logger.info("Главное окно отображено")
                sys.exit(app.exec())
            else:
                logger.info(f"Автовход не удался для {username}: {data.get('error', 'Неизвестная ошибка')}")
        except requests.RequestException as e:
            logger.error(f"Ошибка автовхода для {username}: {e}")
            offline_mode = True

    login_dialog = LoginDialog()
    if login_dialog.exec() != QDialog.Accepted:
        logger.info("Авторизация отменена, выход из приложения")
        sys.exit()

    username, password, offline_mode, remember_me = login_dialog.get_credentials()
    server_builds = []
    license_expiry = "N/A"
    role = "Player"

    if not offline_mode:
        try:
            response = requests.post(f"{SERVER_URL}/api/auth", json={
                "action": "login",
                "username": username,
                "password": password
            }, timeout=5)
            data = response.json()
            if response.status_code == 200 and data.get("status") == "success":
                server_builds = data.get("builds", [])
                license_expiry = data.get("license_expiry", "N/A")
                role = data.get("role", "Player")
                logger.info(f"Успешная авторизация для {username}, сборки: {server_builds}, role: {role}")
                if remember_me:
                    saved_credentials["username"] = username
                    saved_credentials["password"] = password
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(saved_credentials, f, indent=4)
                        logger.info(f"Сохранены данные для автовхода: {username}")
            elif response.status_code == 400 and data.get("status") == "offline":
                offline_mode = True
                server_builds = data.get("builds", [])
                role = data.get("role", "Player")
                logger.info(f"Оффлайн-режим для {username} из-за просроченной лицензии: {data.get('message')}")
            else:
                logger.error(f"Ошибка авторизации: {data.get('error', 'Неизвестная ошибка')}")
                QMessageBox.critical(None, "Ошибка", f"Ошибка авторизации: {data.get('error', 'Неизвестная ошибка')}")
                offline_mode = True
        except requests.RequestException as e:
            logger.error(f"Ошибка подключения к серверу: {e}")
            QMessageBox.critical(None, "Ошибка", "Нет подключения к серверу")
            offline_mode = True

    launcher = LauncherWindow(username, offline_mode, server_builds, license_expiry, role)
    launcher.show()
    launcher.activateWindow()

    logger.info("Главное окно отображено")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()