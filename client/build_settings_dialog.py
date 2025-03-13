import os
import shutil
import logging
from PySide6.QtWidgets import (QDialog, QLineEdit, QDialogButtonBox, QVBoxLayout, QLabel, QTabWidget, QWidget,
                               QListWidget, QTextEdit, QHBoxLayout, QPushButton, QMessageBox)
from PySide6.QtCore import Qt, Signal
from .constants import MODRINTH_STYLE, INSTANCES_DIR, SERVER_INSTANCES_DIR

logger = logging.getLogger(__name__)

class BuildSettingsDialog(QDialog):
    build_deleted = Signal(str)  # Сигнал для уведомления об удалении сборки

    def __init__(self, build_widget, parent=None):
        super().__init__(parent)
        logger.info(f"Создание диалога настроек для сборки: {build_widget.version}")
        self.build_widget = build_widget
        self.setWindowTitle(f"Настройки сборки: {build_widget.version}")
        self.setFixedSize(600, 400)
        self.setStyleSheet(MODRINTH_STYLE)

        # Основной layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Горизонтальные табы
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        main_layout.addWidget(self.tab_widget)

        # Вкладка "Настройки"
        self.settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        self.settings_tab.setLayout(settings_layout)

        java_path_label = QLabel("Путь к Java:")
        self.java_path_input = QLineEdit(self.build_widget.settings.get("java_path", ""))
        settings_layout.addWidget(java_path_label)
        settings_layout.addWidget(self.java_path_input)

        jvm_args_label = QLabel("Аргументы JVM:")
        self.jvm_args_input = QLineEdit(self.build_widget.settings.get("jvm_args", ""))
        settings_layout.addWidget(jvm_args_label)
        settings_layout.addWidget(self.jvm_args_input)

        game_args_label = QLabel("Аргументы игры:")
        self.game_args_input = QLineEdit(self.build_widget.settings.get("game_args", ""))
        settings_layout.addWidget(game_args_label)
        settings_layout.addWidget(self.game_args_input)

        memory_label = QLabel("Память (например, 2G):")
        self.memory_input = QLineEdit(self.build_widget.settings.get("memory", "2G"))
        settings_layout.addWidget(memory_label)
        settings_layout.addWidget(self.memory_input)

        # Кнопки
        button_layout = QHBoxLayout()
        settings_layout.addLayout(button_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)

        delete_button = QPushButton("Удалить сборку")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #e63946; /* Тёмно-красный фон */
                color: white;
                padding: 5px 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f94144; /* Светлее при наведении */
            }
            QPushButton:pressed {
                background-color: #d00000; /* Темнее при нажатии */
            }
        """)
        delete_button.clicked.connect(self.delete_build)
        button_layout.addWidget(delete_button)

        settings_layout.addStretch()

        # Вкладка "Миры"
        self.worlds_tab = QWidget()
        worlds_layout = QVBoxLayout()
        self.worlds_tab.setLayout(worlds_layout)
        self.worlds_list = QListWidget()
        worlds_layout.addWidget(QLabel("Список миров:"))
        worlds_layout.addWidget(self.worlds_list)
        self.load_worlds()

        # Вкладка "Ресурспаки"
        self.resourcepacks_tab = QWidget()
        resourcepacks_layout = QVBoxLayout()
        self.resourcepacks_tab.setLayout(resourcepacks_layout)
        self.resourcepacks_list = QListWidget()
        resourcepacks_layout.addWidget(QLabel("Список ресурспаков:"))
        resourcepacks_layout.addWidget(self.resourcepacks_list)
        self.load_resourcepacks()

        # Вкладка "Моды"
        self.mods_tab = QWidget()
        mods_layout = QVBoxLayout()
        self.mods_tab.setLayout(mods_layout)
        self.mods_list = QListWidget()
        mods_layout.addWidget(QLabel("Список модов:"))
        mods_layout.addWidget(self.mods_list)
        self.load_mods()

        # Вкладка "Логи"
        self.logs_tab = QWidget()
        logs_layout = QVBoxLayout()
        self.logs_tab.setLayout(logs_layout)
        self.logs_list = QListWidget()
        self.logs_list.itemClicked.connect(self.display_log)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        logs_layout.addWidget(QLabel("Список логов:"))
        logs_layout.addWidget(self.logs_list)
        logs_layout.addWidget(QLabel("Содержимое лога:"))
        logs_layout.addWidget(self.log_display)
        self.load_logs()

        # Добавляем вкладки в QTabWidget
        self.tab_widget.addTab(self.settings_tab, "Настройки")
        self.tab_widget.addTab(self.worlds_tab, "Миры")
        self.tab_widget.addTab(self.resourcepacks_tab, "Ресурспаки")
        self.tab_widget.addTab(self.mods_tab, "Моды")
        self.tab_widget.addTab(self.logs_tab, "Логи")

    def save_settings(self):
        self.build_widget.settings["java_path"] = self.java_path_input.text()
        self.build_widget.settings["jvm_args"] = self.jvm_args_input.text()
        self.build_widget.settings["game_args"] = self.game_args_input.text()
        self.build_widget.settings["memory"] = self.memory_input.text()
        self.build_widget.save_settings()
        self.accept()

    def delete_build(self):
        """Удаляет сборку, отправляет сигнал и закрывает диалог"""
        reply = QMessageBox.question(self, "Удаление сборки",
                                     f"Вы уверены, что хотите удалить сборку '{self.build_widget.version}'? Это действие нельзя отменить.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            instance_dir = self.get_instance_dir()
            build_path = os.path.join(instance_dir, self.build_widget.version)
            try:
                if os.path.exists(build_path):
                    shutil.rmtree(build_path)
                    logger.info(f"Сборка {self.build_widget.version} успешно удалена из {build_path}")
                    QMessageBox.information(self, "Успех", f"Сборка '{self.build_widget.version}' удалена.")
                    self.build_deleted.emit(self.build_widget.version)  # Отправляем сигнал об удалении
                    self.accept()  # Закрываем диалог
                else:
                    logger.warning(f"Папка сборки {build_path} не найдена")
                    QMessageBox.warning(self, "Предупреждение", f"Сборка '{self.build_widget.version}' не найдена.")
            except Exception as e:
                logger.error(f"Ошибка удаления сборки {self.build_widget.version}: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить сборку: {e}")
        else:
            logger.info(f"Удаление сборки {self.build_widget.version} отменено пользователем")

    def get_instance_dir(self):
        """Возвращает путь к директории сборки"""
        return SERVER_INSTANCES_DIR if self.build_widget.is_server else INSTANCES_DIR

    def load_worlds(self):
        """Загружает список миров из папки saves"""
        instance_dir = self.get_instance_dir()
        saves_dir = os.path.join(instance_dir, self.build_widget.version, "saves")
        self.worlds_list.clear()
        if os.path.exists(saves_dir):
            for world in os.listdir(saves_dir):
                if os.path.isdir(os.path.join(saves_dir, world)):
                    self.worlds_list.addItem(world)
        else:
            self.worlds_list.addItem("Миров не найдено")

    def load_resourcepacks(self):
        """Загружает список ресурспаков из папки resourcepacks"""
        instance_dir = self.get_instance_dir()
        resourcepacks_dir = os.path.join(instance_dir, self.build_widget.version, "resourcepacks")
        self.resourcepacks_list.clear()
        if os.path.exists(resourcepacks_dir):
            for rp in os.listdir(resourcepacks_dir):
                if rp.endswith((".zip", ".jar")):
                    self.resourcepacks_list.addItem(rp)
        else:
            self.resourcepacks_list.addItem("Ресурспаков не найдено")

    def load_mods(self):
        """Загружает список модов из папки mods"""
        instance_dir = self.get_instance_dir()
        mods_dir = os.path.join(instance_dir, self.build_widget.version, "mods")
        self.mods_list.clear()
        if os.path.exists(mods_dir):
            for mod in os.listdir(mods_dir):
                if mod.endswith((".jar", ".zip")):
                    self.mods_list.addItem(mod)
        else:
            self.mods_list.addItem("Модов не найдено")

    def load_logs(self):
        """Загружает список логов из папки logs"""
        instance_dir = self.get_instance_dir()
        logs_dir = os.path.join(instance_dir, self.build_widget.version, "logs")
        self.logs_list.clear()
        if os.path.exists(logs_dir):
            for log in os.listdir(logs_dir):
                if log.endswith(".log"):
                    self.logs_list.addItem(log)
        else:
            self.logs_list.addItem("Логов не найдено")

    def display_log(self, item):
        """Отображает содержимое выбранного лога"""
        instance_dir = self.get_instance_dir()
        logs_dir = os.path.join(instance_dir, self.build_widget.version, "logs")
        log_file = os.path.join(logs_dir, item.text())
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                self.log_display.setText(f.read())
        except Exception as e:
            logger.error(f"Ошибка чтения лога {log_file}: {e}")
            self.log_display.setText(f"Ошибка чтения лога: {e}")