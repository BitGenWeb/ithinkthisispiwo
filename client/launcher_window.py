import os
import json
import subprocess
import zipfile
import platform

import requests
import logging
from PySide6.QtWidgets import (QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QPushButton,
                               QMessageBox, QTabWidget, QComboBox, QDialog, QApplication,
                               QLineEdit)
from PySide6.QtCore import Qt, QProcess, QProcessEnvironment
from PySide6.QtGui import QFont, QIcon, QColor

from .build_settings_dialog import BuildSettingsDialog
from .constants import MODRINTH_STYLE, INSTANCES_DIR, SERVER_INSTANCES_DIR, SERVER_URL, BASE_DIR
from .build_widget import BuildWidget
from .build_graphics_view import BuildGraphicsView
from .install_worker import InstallWorker
from .launcher_settings_dialog import LauncherSettingsDialog
from .login_dialog import LoginDialog
from .utils import calculate_folder_hash
import minecraft_launcher_lib

logger = logging.getLogger(__name__)

class LauncherWindow(QMainWindow):
    builds = []

    def __init__(self, username, offline_mode=False, server_builds=None, license_expiry=None, role="Player", uuid=None):
        super().__init__()
        self.username = username
        self.offline_mode = offline_mode
        self.server_builds = server_builds or []
        self.license_expiry = license_expiry or "N/A"
        self.role = role
        self.uuid = uuid
        self.minecraft_process = None  # Инициализация атрибута
        self.current_worker = None  # Инициализация атрибута
        logger.info(f"Инициализация LauncherWindow: username={username}, offline_mode={offline_mode}, uuid={uuid}")
        self.builds = []
        self.client_builds_layout = None
        self.server_builds_layout = None
        self.tab_widget = None
        self.install_progress_label = QLabel("Прогресс установки: Ожидание...")
        self.install_progress_label.setVisible(False)
        self.install_progress_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.install_progress_label.setStyleSheet(
            "color: #00ff00; background-color: #252525; padding: 5px; border: 1px solid #353535;")
        self.install_progress_label.setFixedHeight(40)
        self.install_btn = QPushButton("Установить")
        self.install_btn.setFocusPolicy(Qt.NoFocus)
        self.setup_window()
        self.init_ui()
        self.load_existing_builds()
        self.create_build_widgets()
        self.check_builds_on_startup()
        LauncherWindow.builds = self.builds

        if self.offline_mode:
            self.tab_widget.setCurrentIndex(1)
        else:
            self.tab_widget.setCurrentIndex(0)

        self.tab_widget.currentChanged.connect(self.check_tab_switch)

    def authenticate(self):
        """Метод авторизации, вызываемый перед созданием окна"""
        config_file = os.path.join(BASE_DIR, "launcher_config.json")
        username = None
        password = None
        offline_mode = False
        server_builds = []
        license_expiry = "N/A"
        role = "Player"
        uuid = None

        # Проверяем конфиг для автовхода
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                username = config.get("username")
                password = config.get("password")

        if not username or not password:
            login_dialog = LoginDialog()
            if login_dialog.exec() == QDialog.Accepted:
                username, password, offline_mode, remember_me = login_dialog.get_credentials()
                if remember_me:
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump({"username": username, "password": password}, f, indent=4)
                        logger.info(f"Сохранены данные для автовхода: {username}")
            else:
                logger.info("Авторизация отменена, выход из приложения")
                QApplication.quit()
                return None

        # Пробуем авторизоваться на сервере
        if not offline_mode:
            try:
                response = requests.post(f"{SERVER_URL}/api/auth", json={
                    "action": "login",
                    "username": username,
                    "password": password
                }, timeout=5)
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "success":
                    server_builds = data.get("builds", [])
                    license_expiry = data.get("license_expiry", "N/A")
                    role = data.get("role", "Player")
                    uuid = data.get("uuid")  # Получаем UUID с сервера
                    logger.info(f"Успешная авторизация для {username}, UUID: {uuid}, сборки: {server_builds}, role: {role}")
                else:
                    logger.error(f"Ошибка авторизации: {data.get('error', 'Неизвестная ошибка')}")
                    offline_mode = True
            except requests.RequestException as e:
                logger.error(f"Ошибка подключения к серверу: {e}")
                offline_mode = True

        # Если оффлайн-режим, генерируем случайный UUID
        if offline_mode and not uuid:
            config_file = os.path.join(BASE_DIR, "launcher_config.json")
            config = {}
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
            uuid = config.get("offline_uuid", str(uuid.uuid4()))
            config["offline_uuid"] = uuid
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            logger.info(f"Оффлайн-режим: использован/сгенерирован UUID {uuid}")

        return {"username": username, "offline_mode": offline_mode, "server_builds": server_builds,
                "license_expiry": license_expiry, "role": role, "uuid": uuid}

    def check_java_compatibility(self, java_path, mc_version):
        try:
            result = subprocess.run([java_path, "-version"], capture_output=True, text=True)
            java_version = result.stderr.split('"')[1]  # Например, "1.8.0_351"
            major_version = int(java_version.split('.')[1])
            mc_major = int(mc_version.split('.')[1])
            logger.info("java: "+java_version+" Path: "+java_path)
            if mc_major >= 17 and major_version < 16:
                return False, "Для Minecraft 1.17+ требуется Java 16+"
            elif mc_major <= 16 and major_version > 8:
                return False, "Для Minecraft 1.16 и ниже рекомендуется Java 8"
            return True, ""
        except Exception as e:
            return False, f"Ошибка проверки Java: {e}"

    @staticmethod
    def get_runtime_java_path(build_path):
        # Определяем платформу и архитектуру
        system = platform.system().lower()  # windows, linux, darwin (macos)
        arch = platform.machine().lower()  # x86_64, x86, amd64, etc.

        # Приводим архитектуру к стандартным значениям
        if arch in ["x86_64", "amd64"]:
            arch = "x64"
        elif arch in ["x86", "i386"]:
            arch = "x32"

        # Возможные имена папок с Java
        runtime_names = ["java-runtime-gamma", "java-runtime-beta", "java-runtime-alpha"]

        # Проверяем все возможные runtime папки
        for runtime_name in runtime_names:
            java_path = os.path.join(build_path, "runtime", runtime_name, f"{system}-{arch}", runtime_name, "bin",
                                     "java")
            if os.path.exists(java_path):
                return java_path

        # Если Java не найдена, возвращаем None
        return None

    def ensure_java_installed(self, build_path, mc_version):
        runtime_path = os.path.join(build_path, "runtime")
        os.makedirs(runtime_path, exist_ok=True)

        # Проверяем, установлена ли Java в runtime папке
        java_path = LauncherWindow.get_runtime_java_path(build_path)
        if not java_path:
            logger.info(f"Java не найдена в runtime папке, начинаем загрузку...")
            self.install_progress_label.setText("Установка Java...")
            self.install_progress_label.setVisible(True)

            # Устанавливаем Java runtime (пробуем установить gamma, если не получится — alpha или beta)
            self.java_worker = InstallWorker(
                minecraft_launcher_lib.runtime.install_jvm_runtime,
                "java-runtime-gamma",  # Пробуем gamma
                runtime_path
            )
            self.java_worker.progress.connect(self.update_install_progress)
            self.java_worker.finished.connect(
                lambda success, msg: self.on_java_install_finished(success, msg, build_path)
            )
            self.java_worker.start()
        else:
            return java_path

    def on_java_install_finished(self, success, message, build_path):
        if success:
            logger.info(f"Java успешно установлена в {build_path}")
            java_path = LauncherWindow.get_runtime_java_path(build_path)
            if java_path:
                self.install_progress_label.setVisible(False)
                return java_path
        else:
            logger.error(f"Ошибка установки Java: {message}")
            self.show_error_dialog(f"Ошибка установки Java: {message}")
            return None

    def run_minecraft(self, build_widget):
        # Проверка Java и другие подготовительные шаги
        java_path = build_widget.settings.get("java_path", "java")
        compatible, message = self.check_java_compatibility(java_path, build_widget.mc_version)

        # Если Java не совместима или не указана, используем Java из runtime папки
        if not compatible or java_path == "java":
            runtime_java_path = self.ensure_java_installed(os.path.join(INSTANCES_DIR, build_widget.version),
                                                      build_widget.mc_version)
            if runtime_java_path:
                java_path = runtime_java_path
                logger.info(f"Используется Java из runtime папки: {java_path}")
            else:
                self.show_error_dialog("Java не найдена в runtime папке и указанная Java не совместима!")
                return

        # Подготовка аргументов запуска
        instance_dir = SERVER_INSTANCES_DIR if build_widget.is_server else INSTANCES_DIR
        build_path = os.path.join(instance_dir, build_widget.version)
        settings = build_widget.settings

        try:
            # Генерация команды запуска
            minecraft_command = self.generate_minecraft_command(build_widget, build_path)
            logger.info(f"Запуск Minecraft с командой: {' '.join(minecraft_command)}")

            # Настройка процесса
            self.minecraft_process = QProcess()
            self.minecraft_process.readyReadStandardOutput.connect(self.handle_mc_output)
            self.minecraft_process.readyReadStandardError.connect(self.handle_mc_error)
            self.minecraft_process.finished.connect(self.handle_mc_finished)

            # Установка окружения
            env = QProcessEnvironment.systemEnvironment()
            self.minecraft_process.setProcessEnvironment(env)
            self.minecraft_process.setWorkingDirectory(build_path)

            # Запуск
            self.hide()
            self.minecraft_process.start(minecraft_command[0], minecraft_command[1:])

        except Exception as e:
            self.show_error_dialog(f"Ошибка запуска Minecraft: {str(e)}")
            logger.error(f"Ошибка запуска: {str(e)}", exc_info=True)
            self.show()

    def handle_mc_output(self):
        if self.minecraft_process:
            data = self.minecraft_process.readAllStandardOutput().data().decode(errors='replace')
            logger.info(f"Minecraft Output: {data.strip()}")

    def handle_mc_error(self):
        if self.minecraft_process:
            error = self.minecraft_process.readAllStandardError().data().decode(errors='replace')
            logger.error(f"Minecraft Error: {error.strip()}")
            if "Error" in error:
                self.show_error_dialog(f"Ошибка Minecraft: {error.split('Error')[1][:100]}...")

    def handle_mc_finished(self, exit_code, exit_status):
        logger.info(f"Minecraft завершился с кодом {exit_code} ({exit_status})")
        self.show()
        self.minecraft_process = None
        if exit_code != 0:
            self.show_error_dialog(f"Minecraft завершился с ошибкой (код: {exit_code})")

    def closeEvent(self, event):
        if self.minecraft_process and self.minecraft_process.state() == QProcess.Running:
            reply = QMessageBox.question(
                self,
                "Закрытие лаунчера",
                "Minecraft всё ещё работает! Вы уверены, что хотите выйти?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.minecraft_process.terminate()
                if not self.minecraft_process.waitForFinished(2000):
                    self.minecraft_process.kill()
                event.accept()
            else:
                event.ignore()
        else:
            if self.current_worker and self.current_worker.isRunning():
                self.current_worker.terminate()
            event.accept()

    def show_login_dialog(self):
        login_dialog = LoginDialog()
        if login_dialog.exec() == QDialog.Accepted:
            username, password, offline_mode, remember_me = login_dialog.get_credentials()
            server_builds = []
            license_expiry = "N/A"
            role = "Player"
            uuid = None

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
                        uuid = data.get("uuid")  # Получаем UUID с сервера
                        logger.info(f"Успешная авторизация для {username}, UUID: {uuid}")
                        if remember_me:
                            config_file = os.path.join(BASE_DIR, "launcher_config.json")
                            config = {}
                            if os.path.exists(config_file):
                                with open(config_file, "r", encoding="utf-8") as f:
                                    config = json.load(f)
                            config["username"] = username
                            config["password"] = password
                            with open(config_file, "w", encoding="utf-8") as f:
                                json.dump(config, f, indent=4)
                                logger.info(f"Сохранены данные для автовхода: {username}")
                    else:
                        logger.error(f"Ошибка авторизации: {data.get('error', 'Неизвестная ошибка')}")
                        offline_mode = True
                except requests.RequestException as e:
                    logger.error(f"Ошибка подключения к серверу: {e}")
                    offline_mode = True

            # Если оффлайн, генерируем UUID
            if offline_mode and not uuid:
                uuid = str(uuid.uuid4())
                logger.info(f"Оффлайн-режим: сгенерирован UUID {uuid}")

            launcher = LauncherWindow(username, offline_mode, server_builds, license_expiry, role, uuid)
            launcher.show()
        else:
            logger.info("Авторизация отменена, выход из приложения")
            QApplication.quit()

    def setup_window(self):
        self.setWindowTitle("SkyZern Launcher")
        self.setFixedSize(800, 600)
        self.setStyleSheet(MODRINTH_STYLE)
        self.setWindowIcon(QIcon.fromTheme("application-x-executable"))
        if self.offline_mode:
            QMessageBox.warning(self, "Оффлайн-режим",
                                "Вы вошли в оффлайн-режиме. Загрузка серверных сборок недоступна.")

    def check_tab_switch(self, index):
        if self.offline_mode and index == 0:
            QMessageBox.warning(
                self,
                "Ограничение",
                "Вы в оффлайн-режиме! Для доступа к серверным сборкам войдите с действующей лицензией."
            )
            self.tab_widget.setCurrentIndex(1)

    def setup_builds_panel(self, main_layout=None):
        if self.tab_widget is None:
            self.tab_widget = QTabWidget()
            self.tab_widget.setTabBarAutoHide(False)
            self.tab_widget.tabBar().setFont(QFont("Segoe UI", 11, QFont.Bold))
            logger.info("Создан QTabWidget для сборок")

        # Серверные сборки
        self.server_tab = QWidget()
        self.tab_widget.addTab(self.server_tab, "Серверные сборки")
        server_layout = QVBoxLayout()
        self.server_tab.setLayout(server_layout)
        self.server_scroll = QScrollArea()
        self.server_scroll.setWidgetResizable(True)
        self.server_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.server_builds_widget = QWidget()
        self.server_builds_layout = QVBoxLayout()
        self.server_builds_layout.setSpacing(2)
        self.server_builds_layout.setContentsMargins(5, 5, 10, 5)
        self.server_builds_layout.setAlignment(Qt.AlignTop)
        self.server_builds_widget.setLayout(self.server_builds_layout)
        self.server_scroll.setWidget(self.server_builds_widget)
        server_layout.addWidget(self.server_scroll)
        logger.info("Инициализирован layout для серверных сборок")

        # Клиентские сборки
        self.client_tab = QWidget()
        self.tab_widget.addTab(self.client_tab, "Клиентские сборки")
        client_layout = QVBoxLayout()
        self.client_tab.setLayout(client_layout)
        self.client_scroll = QScrollArea()
        self.client_scroll.setWidgetResizable(True)
        self.client_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.client_builds_widget = QWidget()
        self.client_builds_layout = QVBoxLayout()
        self.client_builds_layout.setSpacing(2)
        self.client_builds_layout.setContentsMargins(5, 5, 10, 5)
        self.client_builds_layout.setAlignment(Qt.AlignTop)
        self.client_builds_widget.setLayout(self.client_builds_layout)
        self.client_scroll.setWidget(self.client_builds_widget)
        client_layout.addWidget(self.client_scroll)
        logger.info("Инициализирован layout для клиентских сборок")

        # Таб установки версий
        self.install_tab = QWidget()
        self.tab_widget.addTab(self.install_tab, "Установка версий")
        install_layout = QVBoxLayout()
        self.install_tab.setLayout(install_layout)

        install_subtabs = QTabWidget()
        install_layout.addWidget(install_subtabs)

        try:
            all_versions = minecraft_launcher_lib.utils.get_version_list()
            release_versions = [v["id"] for v in all_versions if v["type"] == "release"]
            logger.info(f"Загружено {len(release_versions)} релизных версий Minecraft")
        except Exception as e:
            logger.error(f"Ошибка загрузки версий Minecraft: {e}")
            release_versions = ["1.20.1", "1.19.2", "1.18.2", "1.16.5"]

        # Ванильное подменю
        vanilla_tab = QWidget()
        install_subtabs.addTab(vanilla_tab, "Vanilla")
        vanilla_layout = QVBoxLayout()
        vanilla_tab.setLayout(vanilla_layout)

        vanilla_version_label = QLabel("Версия Minecraft:")
        self.vanilla_version_combo = QComboBox()
        self.vanilla_version_combo.addItems(release_versions)
        self.vanilla_version_combo.setCurrentText("1.20.1")
        vanilla_layout.addWidget(vanilla_version_label)
        vanilla_layout.addWidget(self.vanilla_version_combo)

        vanilla_name_label = QLabel("Название сборки:")
        self.vanilla_name_input = QLineEdit()
        self.vanilla_name_input.setPlaceholderText("Например: Vanilla 1.20.1")
        vanilla_layout.addWidget(vanilla_name_label)
        vanilla_layout.addWidget(self.vanilla_name_input)

        self.install_btn.clicked.connect(self.start_vanilla_install)
        vanilla_layout.addWidget(self.install_btn)
        vanilla_layout.addWidget(self.install_progress_label)
        vanilla_layout.addStretch()

        # Forge подменю
        forge_tab = QWidget()
        install_subtabs.addTab(forge_tab, "Forge")
        forge_layout = QVBoxLayout()
        forge_tab.setLayout(forge_layout)

        forge_version_label = QLabel("Версия Minecraft:")
        self.forge_version_combo = QComboBox()
        self.forge_version_combo.addItems(release_versions)
        self.forge_version_combo.setCurrentText("1.20.1")
        self.forge_version_combo.currentTextChanged.connect(self.update_forge_versions)
        forge_layout.addWidget(forge_version_label)
        forge_layout.addWidget(self.forge_version_combo)

        forge_loader_label = QLabel("Версия Forge:")
        self.forge_loader_combo = QComboBox()
        self.forge_loader_combo.currentIndexChanged.connect(self.update_forge_recommended)
        forge_layout.addWidget(forge_loader_label)
        forge_layout.addWidget(self.forge_loader_combo)

        forge_name_label = QLabel("Название сборки:")
        self.forge_name_input = QLineEdit()
        self.forge_name_input.setPlaceholderText("Например: Forge 1.16.5")
        forge_layout.addWidget(forge_name_label)
        forge_layout.addWidget(self.forge_name_input)

        forge_install_btn = QPushButton("Установить")
        forge_install_btn.setFocusPolicy(Qt.NoFocus)
        forge_install_btn.clicked.connect(self.start_forge_install)
        forge_layout.addWidget(forge_install_btn)
        forge_layout.addWidget(self.install_progress_label)
        forge_layout.addStretch()

        # Fabric подменю
        fabric_tab = QWidget()
        install_subtabs.addTab(fabric_tab, "Fabric")
        fabric_layout = QVBoxLayout()
        fabric_tab.setLayout(fabric_layout)

        fabric_version_label = QLabel("Версия Minecraft:")
        self.fabric_version_combo = QComboBox()
        self.fabric_version_combo.addItems(release_versions)
        self.fabric_version_combo.setCurrentText("1.20.1")
        self.fabric_version_combo.currentTextChanged.connect(self.update_fabric_versions)
        fabric_layout.addWidget(fabric_version_label)
        fabric_layout.addWidget(self.fabric_version_combo)

        fabric_loader_label = QLabel("Версия Fabric:")
        self.fabric_loader_combo = QComboBox()
        self.fabric_loader_combo.currentIndexChanged.connect(self.update_fabric_recommended)
        fabric_layout.addWidget(fabric_loader_label)
        fabric_layout.addWidget(self.fabric_loader_combo)

        fabric_name_label = QLabel("Название сборки:")
        self.fabric_name_input = QLineEdit()
        self.fabric_name_input.setPlaceholderText("Например: Fabric 1.19.2")
        fabric_layout.addWidget(fabric_name_label)
        fabric_layout.addWidget(self.fabric_name_input)

        fabric_install_btn = QPushButton("Установить")
        fabric_install_btn.setFocusPolicy(Qt.NoFocus)
        fabric_install_btn.clicked.connect(self.start_fabric_install)
        fabric_layout.addWidget(fabric_install_btn)
        fabric_layout.addWidget(self.install_progress_label)
        fabric_layout.addStretch()

        self.update_forge_versions()
        self.update_fabric_versions()

        if main_layout:
            main_layout.addWidget(self.tab_widget)
            logger.info("QTabWidget добавлен в главный layout")

    def create_build_widgets(self):
        for build in self.server_builds:
            self.add_build(build["name"], build["mc_version"], build["modloader"], is_server=True)

    def check_builds_on_startup(self):
        if self.offline_mode:
            logger.info("Оффлайн-режим: проверка сборок пропущена")
            return

        logger.info("Проверка наличия и актуальности серверных сборок при запуске...")
        for build in self.builds:
            if build.is_server:
                instance_dir = SERVER_INSTANCES_DIR
                build_path = os.path.join(instance_dir, build.version)
                client_hash = calculate_folder_hash(build_path)
                if not client_hash:
                    logger.warning(f"Сборка {build.version} отсутствует или повреждена")
                    build.set_install_state(True)
                else:
                    self.check_server_build(build, client_hash)

    def check_server_build(self, build, client_hash):
        try:
            response = requests.get(f"{SERVER_URL}/api/check_build/{build.version}", timeout=5)
            data = response.json()
            server_hash = data.get("hash")
            if server_hash != client_hash:
                logger.info(f"Сборка {build.version} устарела, требуется обновление")
                build.set_install_state(True)
            else:
                logger.info(f"Сборка {build.version} актуальна")
                build.set_install_state(False)
        except requests.RequestException as e:
            logger.error(f"Ошибка проверки сборки {build.version}: {e}")
            build.set_install_state(True)

    def init_ui(self):
        logger.info("Начало init_ui")
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        self.setup_account_panel(main_layout)
        self.setup_builds_panel(main_layout)
        logger.info("Конец init_ui")

    def setup_account_panel(self, main_layout):
        account_frame = QFrame()
        account_frame.setObjectName("account_frame")
        account_frame.setFixedWidth(220)
        account_layout = QVBoxLayout()
        account_layout.setContentsMargins(15, 25, 15, 15)
        account_frame.setLayout(account_layout)

        avatar_label = QLabel("👤")
        avatar_label.setAlignment(Qt.AlignCenter)
        avatar_label.setStyleSheet("font-size: 56px; border-radius: 50%; background: #353535; padding: 10px;")
        account_layout.addWidget(avatar_label)

        self.account_name = QLabel(self.username)
        self.account_name.setFont(QFont('Arial', 14, QFont.Bold))
        self.account_status = QLabel("● Оффлайн" if self.offline_mode else "● Онлайн")
        self.account_status.setStyleSheet(f"color: {'#ff5555' if self.offline_mode else '#00ff00'}; font-size: 12px;")
        self.account_role = QLabel(f"Роль: {self.role}")
        self.license_expiry_label = QLabel(f"Лицензия до: {self.license_expiry}")

        for widget in [self.account_name, self.account_status,
                       self.account_role, self.license_expiry_label]:
            widget.setAlignment(Qt.AlignCenter)
            account_layout.addWidget(widget)

        settings_btn = QPushButton("Настройки")
        settings_btn.clicked.connect(self.open_launcher_settings)
        settings_btn.setFixedHeight(40)
        account_layout.addWidget(settings_btn)

        logout_btn = QPushButton("Выйти")
        logout_btn.clicked.connect(self.logout)
        logout_btn.setObjectName("logout_btn")
        logout_btn.setFixedHeight(40)
        account_layout.addWidget(logout_btn)

        account_layout.addStretch()
        main_layout.addWidget(account_frame)

    def logout(self):
        logger.info(f"Выход из аккаунта для {self.username}")
        config_file = os.path.join(BASE_DIR, "launcher_config.json")

        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            config.pop("username", None)
            config.pop("password", None)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            logger.info("Данные авторизации удалены из конфигурации")

        self.close()
        self.show_login_dialog()

    def open_launcher_settings(self):
        dialog = LauncherSettingsDialog(self)
        dialog.exec()

    def add_build(self, version, mc_version, modloader, is_server=True):
        build = BuildWidget(version, mc_version, modloader, is_server)
        graphics_view = BuildGraphicsView(build)
        build.playRequested.connect(self.handle_play)
        build.settingsRequested.connect(self.handle_settings)
        build.installRequested.connect(lambda: self.handle_install(build))
        if is_server and self.server_builds_layout is not None:
            self.server_builds_layout.addWidget(graphics_view, alignment=Qt.AlignTop)
        elif not is_server and self.client_builds_layout is not None:
            self.client_builds_layout.addWidget(graphics_view, alignment=Qt.AlignTop)
        else:
            logger.warning(f"Не удалось добавить сборку {version}: layout не инициализирован")
        self.builds.append(build)

    def handle_play(self):
        sender = self.sender()
        instance_dir = SERVER_INSTANCES_DIR if sender.is_server else INSTANCES_DIR
        build_path = os.path.join(instance_dir, sender.version)

        client_hash = calculate_folder_hash(build_path)
        if not client_hash:
            logger.warning(f"Сборка {sender.version} отсутствует или повреждена")
            if sender.is_server and not self.offline_mode:
                logger.info(f"Установка уведомления для сборки {sender.version}")
                sender.set_install_state(True)
            else:
                self.show_error_dialog(f"Сборка {sender.version} не установлена!")
            return

        if sender.is_server and not self.offline_mode:
            self.check_server_build(sender, client_hash)
        else:
            self.run_minecraft(sender)

    def handle_settings(self):
        sender = self.sender()
        if isinstance(sender, BuildWidget) and not sender._install_state:
            dialog = BuildSettingsDialog(sender, self)
            dialog.build_deleted.connect(self.remove_build_widget)
            dialog.exec()

    def handle_install(self, build):
        logger.info(f"Запрошена установка сборки {build.version}")
        self.download_build(build.version, build, self)

    def download_build(self, build_name, build_widget=None, launcher_instance=None):
        try:
            response = requests.get(f"{SERVER_URL}/api/download_build/{build_name}", timeout=5)
            response.raise_for_status()

            logger.info(f"Скачивание сборки {build_name}")
            instance_path = os.path.join(
                SERVER_INSTANCES_DIR if build_widget and build_widget.is_server else INSTANCES_DIR,
                build_name
            )
            os.makedirs(instance_path, exist_ok=True)
            zip_path = os.path.join(instance_path, f"{build_name}.zip")

            with open(zip_path, "wb") as f:
                f.write(response.content)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(instance_path)
            os.remove(zip_path)

            if build_widget:
                build_widget.set_install_state(False)
                logger.info(f"Запуск сборки {build_name} после скачивания")
                if launcher_instance:
                    launcher_instance.run_minecraft(build_widget)

        except requests.RequestException as e:
            logger.error(f"Ошибка подключения к серверу при скачивании {build_name}: {e}")
            QMessageBox.critical(None, "Ошибка", f"Ошибка скачивания: {str(e)}")
        except zipfile.BadZipFile as e:
            logger.error(f"Ошибка распаковки архива {build_name}: {e}")
            QMessageBox.critical(None, "Ошибка", "Получен некорректный архив")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при скачивании {build_name}: {e}")
            QMessageBox.critical(None, "Ошибка", "Что-то пошло не так")

    def handle_process_output(self):
        output = self.current_process.readAllStandardOutput().data().decode(errors='replace')
        logger.info(f"Вывод Minecraft: {output}")

    def handle_process_error(self):
        error_output = self.current_process.readAllStandardError().data().decode(errors='replace')
        logger.error(f"Ошибка Minecraft: {error_output}")
        self.show_error_dialog(f"Ошибка Minecraft:\n{error_output}")

    def handle_process_finished(self, exit_code, exit_status):
        logger.info(f"Процесс Minecraft завершен с кодом: {exit_code}, статус: {exit_status}")
        self.show()
        if exit_code != 0:
            self.show_error_dialog("Ошибка запуска Minecraft!")
        else:
            logger.info("Minecraft успешно завершён")

    def show_error_dialog(self, message):
        logger.error(f"Ошибка: {message}")
        QMessageBox.critical(self, "Ошибка", message)

    def update_forge_versions(self):
        version = self.forge_version_combo.currentText()
        try:
            forge_versions = minecraft_launcher_lib.forge.list_forge_versions()
            compatible_versions = [v for v in forge_versions if v.startswith(version + "-")]
            self.forge_loader_combo.clear()
            recommended_version = minecraft_launcher_lib.forge.find_forge_version(version)
            for fv in compatible_versions:
                if fv == recommended_version:
                    self.forge_loader_combo.addItem(f"{fv} (Рекомендуемая)", fv)
                    self.forge_loader_combo.setItemData(self.forge_loader_combo.count() - 1, QColor("#00ff00"),
                                                        Qt.ForegroundRole)
                else:
                    self.forge_loader_combo.addItem(fv, fv)
        except Exception as e:
            logger.error(f"Ошибка получения версий Forge: {e}")
            self.show_error_dialog(f"Не удалось загрузить версии Forge: {e}")

    def update_fabric_versions(self):
        version = self.fabric_version_combo.currentText()
        try:
            fabric_versions = minecraft_launcher_lib.fabric.get_all_loader_versions()
            self.fabric_loader_combo.clear()
            latest_version = fabric_versions[0]["version"]
            for fv in fabric_versions:
                if fv["version"] == latest_version:
                    self.fabric_loader_combo.addItem(f"{fv['version']} (Рекомендуемая)", fv['version'])
                    self.fabric_loader_combo.setItemData(self.fabric_loader_combo.count() - 1, QColor("#00ff00"),
                                                        Qt.ForegroundRole)
                else:
                    self.fabric_loader_combo.addItem(fv['version'], fv['version'])
        except Exception as e:
            logger.error(f"Ошибка получения версий Fabric: {e}")
            self.show_error_dialog(f"Не удалось загрузить версии Fabric: {e}")

    def update_forge_recommended(self):
        version = self.forge_version_combo.currentText()
        recommended_version = minecraft_launcher_lib.forge.find_forge_version(version)
        for i in range(self.forge_loader_combo.count()):
            fv = self.forge_loader_combo.itemData(i)
            if fv == recommended_version:
                self.forge_loader_combo.setItemData(i, QColor("#00ff00"), Qt.ForegroundRole)
            else:
                self.forge_loader_combo.setItemData(i, QColor("#e0e0e0"), Qt.ForegroundRole)

    def update_fabric_recommended(self):
        latest_version = minecraft_launcher_lib.fabric.get_all_loader_versions()[0]["version"]
        for i in range(self.fabric_loader_combo.count()):
            fv = self.fabric_loader_combo.itemData(i)
            if fv == latest_version:
                self.fabric_loader_combo.setItemData(i, QColor("#00ff00"), Qt.ForegroundRole)
            else:
                self.fabric_loader_combo.setItemData(i, QColor("#e0e0e0"), Qt.ForegroundRole)

    def start_install(self, install_type):
        logger.info(f"Вызов start_install для {install_type}")
        combos = {
            "vanilla": (self.vanilla_version_combo, self.vanilla_name_input, self.install_btn),
            "forge": (self.forge_version_combo, self.forge_name_input, self.install_btn),
            "fabric": (self.fabric_version_combo, self.fabric_name_input, self.install_btn)
        }
        version_combo, name_input, install_btn = combos[install_type]
        version = version_combo.currentText()
        build_name = name_input.text().strip()
        if not build_name:
            self.show_error_dialog("Введите название сборки!")
            return

        build_path = os.path.join(INSTANCES_DIR, build_name)
        os.makedirs(build_path, exist_ok=True)

        install_btn.setEnabled(False)
        self.install_progress_label.setText("Прогресс установки: Начало...")
        self.install_progress_label.setVisible(True)

        if install_type == "vanilla":
            install_func = minecraft_launcher_lib.install.install_minecraft_version
            args = (version, build_path)
            modloader = ""
        elif install_type == "forge":
            forge_version = self.forge_loader_combo.currentData()
            install_func = minecraft_launcher_lib.forge.install_forge_version
            args = (f"{version}-{forge_version}", build_path)
            modloader = f"Forge {forge_version}"
        elif install_type == "fabric":
            fabric_version = self.fabric_loader_combo.currentData()
            install_func = minecraft_launcher_lib.fabric.install_fabric
            args = (version, build_path, fabric_version)
            modloader = f"Fabric {fabric_version}"

        self.worker = InstallWorker(install_func, *args)
        self.worker.progress.connect(self.update_install_progress)
        self.worker.finished.connect(
            lambda success, msg: self.finish_install(success, msg, install_btn, self.install_progress_label,
                                                     build_name, version, modloader)
        )
        self.worker.start()

    def start_vanilla_install(self):
        self.start_install("vanilla")

    def start_forge_install(self):
        self.start_install("forge")

    def start_fabric_install(self):
        self.start_install("fabric")

    def update_install_progress(self, message):
        logger.info(f"Обновление прогресса: {message}")
        self.install_progress_label.setText(message)

    def finish_install(self, success, message, install_btn, progress_label, build_name, version, modloader):
        logger.info(f"Завершение установки: success={success}, message={message}, build_name={build_name}")
        if install_btn is not None:
            install_btn.setEnabled(True)
        progress_label.setVisible(False)
        if success:
            self.add_build(build_name, version, modloader, is_server=False)
            build_path = os.path.join(INSTANCES_DIR, build_name)
            settings_file = os.path.join(build_path, f"{build_name}.json")
            default_settings = {
                "java_path": "java",
                "jvm_args": "",
                "game_args": "",
                "memory": "2G",
                "mc_version": version,
                "modloader": modloader
            }
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(default_settings, f, indent=4)
            QMessageBox.information(self, "Успех", message)
        else:
            self.show_error_dialog(message)

    def load_existing_builds(self):
        """Загружает существующие сборки из INSTANCES_DIR и SERVER_INSTANCES_DIR"""
        if os.path.exists(INSTANCES_DIR):
            for build_name in os.listdir(INSTANCES_DIR):
                build_path = os.path.join(INSTANCES_DIR, build_name)
                if os.path.isdir(build_path):
                    settings_file = os.path.join(build_path, f"{build_name}.json")
                    if os.path.exists(settings_file):
                        with open(settings_file, "r", encoding="utf-8") as f:
                            settings = json.load(f)
                        mc_version = settings.get("mc_version", "Unknown")
                        modloader = settings.get("modloader", "Unknown")
                        self.add_build(build_name, mc_version, modloader, is_server=False)
                    else:
                        logger.warning(f"Не найден файл настроек для сборки {build_name}")

        if not self.offline_mode and os.path.exists(SERVER_INSTANCES_DIR):
            for build_name in os.listdir(SERVER_INSTANCES_DIR):
                build_path = os.path.join(SERVER_INSTANCES_DIR, build_name)
                if os.path.isdir(build_path):
                    settings_file = os.path.join(build_path, f"{build_name}.json")
                    if os.path.exists(settings_file):
                        with open(settings_file, "r", encoding="utf-8") as f:
                            settings = json.load(f)
                        mc_version = settings.get("mc_version", "Unknown")
                        modloader = settings.get("modloader", "Unknown")
                        self.add_build(build_name, mc_version, modloader, is_server=True)
                    else:
                        logger.warning(f"Не найден файл настроек для серверной сборки {build_name}")

    def remove_build_widget(self, build_version):
        """Удаляет виджет сборки из списка и интерфейса"""
        for i, build in enumerate(self.builds):
            if build.version == build_version:
                self.builds.pop(i)
                widget = self.client_builds_layout.itemAt(i).widget()
                if widget:
                    self.client_builds_layout.removeWidget(widget)
                    widget.deleteLater()
                    logger.info(f"Виджет сборки {build_version} удалён из интерфейса")
                break
        LauncherWindow.builds = self.builds