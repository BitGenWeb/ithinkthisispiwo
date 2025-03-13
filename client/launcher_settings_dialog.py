import os
import json
import logging
from PySide6.QtWidgets import (QDialog, QLineEdit, QComboBox, QCheckBox, QDialogButtonBox, QVBoxLayout, QLabel)
from .constants import MODRINTH_STYLE, BASE_DIR

logger = logging.getLogger(__name__)

class LauncherSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Инициализация диалога настроек лаунчера")
        self.setWindowTitle("Настройки лаунчера")
        self.setFixedSize(400, 350)
        self.setStyleSheet(MODRINTH_STYLE)

        self.settings_file = os.path.join(BASE_DIR, "launcher_config.json")
        self.load_settings()

        layout = QVBoxLayout()
        self.setLayout(layout)

        minecraft_dir_label = QLabel("Путь к папке Minecraft:")
        self.minecraft_dir_input = QLineEdit(self.settings.get("minecraft_dir", ""))
        layout.addWidget(minecraft_dir_label)
        layout.addWidget(self.minecraft_dir_input)

        minecraft_path_label = QLabel("Путь к Minecraft JAR:")
        self.minecraft_path_input = QLineEdit(self.settings.get("minecraft_path", ""))
        layout.addWidget(minecraft_path_label)
        layout.addWidget(self.minecraft_path_input)

        language_label = QLabel("Язык интерфейса:")
        self.language_input = QLineEdit(self.settings.get("language", "ru"))
        layout.addWidget(language_label)
        layout.addWidget(self.language_input)

        theme_label = QLabel("Тема оформления:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Темная", "Светлая"])
        self.theme_combo.setCurrentText(self.settings.get("theme", "Темная"))
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)

        self.auto_launch_checkbox = QCheckBox("Автоматический запуск игры при выборе")
        self.auto_launch_checkbox.setChecked(self.settings.get("auto_launch", False))
        layout.addWidget(self.auto_launch_checkbox)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r", encoding="utf-8") as f:
                self.settings = json.load(f)
        else:
            self.settings = {
                "minecraft_dir": "",
                "minecraft_path": "",
                "language": "ru",
                "theme": "Темная",
                "auto_launch": False
            }

    def save_settings(self):
        self.settings["minecraft_dir"] = self.minecraft_dir_input.text()
        self.settings["minecraft_path"] = self.minecraft_path_input.text()
        self.settings["language"] = self.language_input.text()
        self.settings["theme"] = self.theme_combo.currentText()
        self.settings["auto_launch"] = self.auto_launch_checkbox.isChecked()
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r", encoding="utf-8") as f:
                current_config = json.load(f)
                current_config.update(self.settings)
                self.settings = current_config
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4)
        self.accept()