import os
import json
import logging

import requests
from PySide6.QtWidgets import (QFrame, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QDialog)
from PySide6.QtCore import Qt, Signal, Property
from PySide6.QtGui import QFont, QCursor, QPainter, QBrush, QColor
from .constants import MODRINTH_STYLE, SERVER_INSTANCES_DIR, INSTANCES_DIR, SERVER_URL
from .build_settings_dialog import BuildSettingsDialog
from .utils import calculate_folder_hash

logger = logging.getLogger(__name__)

class BuildWidget(QFrame):
    playRequested = Signal()
    settingsRequested = Signal()
    installRequested = Signal()

    def __init__(self, version, mc_version, modloader, is_server=False):
        super().__init__()
        self._bg_color = QColor("#252525")
        self.version = version
        self.mc_version = mc_version
        self.modloader = modloader
        self.is_server = is_server
        self._install_state = False
        self.setup_ui(version, mc_version, modloader)
        self.load_settings()

    def load_settings(self):
        instance_dir = SERVER_INSTANCES_DIR if self.is_server else INSTANCES_DIR
        self.settings_file = os.path.join(instance_dir, f"{self.version}.json")
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r", encoding="utf-8") as f:
                self.settings = json.load(f)
        else:
            self.settings = {
                "java_path": "java",
                "jvm_args": "",
                "game_args": "",
                "memory": "2G"
            }
            self.save_settings()

    def save_settings(self):
        instance_dir = SERVER_INSTANCES_DIR if self.is_server else INSTANCES_DIR
        os.makedirs(instance_dir, exist_ok=True)
        with open(os.path.join(instance_dir, f"{self.version}.json"), "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4)

    def open_settings_dialog(self):
        logger.info(f"Открытие настроек для сборки: {self.version}")
        dialog = BuildSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            logger.info(f"Настройки для {self.version} сохранены")
            self.save_settings()
        else:
            logger.info(f"Настройки для {self.version} отменены")

    def setup_ui(self, version, mc_version, modloader):
        self.setObjectName("build_frame")
        self.setFixedHeight(90)
        self.setFixedWidth(400)
        logger.info(f"Инициализация UI для сборки {version}: кнопки должны быть видны")

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)

        icon_label = QLabel("📦")
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 24px;")

        self.buttons_frame = QFrame()
        self.buttons_frame.setObjectName("buttons_frame")
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(2)
        self.buttons_frame.setLayout(buttons_layout)
        self.buttons_frame.setMinimumWidth(120)

        self.play_btn = QPushButton("Играть")
        self.settings_btn = QPushButton("Настройки")
        self.install_btn = QPushButton("Установить")
        self.install_btn.setObjectName("install_btn")

        self.play_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.settings_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.install_btn.setCursor(QCursor(Qt.PointingHandCursor))

        buttons_layout.addWidget(self.play_btn)
        buttons_layout.addWidget(self.settings_btn)
        buttons_layout.addWidget(self.install_btn)

        content_frame = QFrame()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(10, 0, 5, 0)
        content_frame.setLayout(content_layout)

        self.title_label = QLabel(version)
        self.title_label.setFont(QFont('Arial', 12, QFont.Bold))
        self.title_label.setObjectName("title_label")

        self.version_label = QLabel(f"{mc_version} | {modloader}")
        self.version_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.version_label.setObjectName("version_label")

        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.version_label)

        main_layout.addWidget(icon_label)
        main_layout.addWidget(content_frame)
        main_layout.addStretch()
        main_layout.addWidget(self.buttons_frame)

        self.setStyleSheet(f"""
            {MODRINTH_STYLE}
            QFrame#build_frame {{
                border-radius: 10px;
                margin: 5px;
                border: 1px solid #353535;
            }}
            QLabel {{
                background-color: transparent;
                color: #e0e0e0;
            }}
            QLabel#title_label {{
                font: bold 12pt 'Arial';
            }}
            QLabel#version_label {{
                color: #aaaaaa;
                font-size: 11px;
            }}
        """)
        self.set_bg_color(self._bg_color)

        self.play_btn.clicked.connect(self.playRequested.emit)
        self.settings_btn.clicked.connect(self.settingsRequested.emit)
        self.install_btn.clicked.connect(self.installRequested.emit)

        self.set_install_state(self._install_state)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._install_state:
            painter = QPainter(self)
            pen = painter.pen()
            pen.setWidth(2)
            pen.setColor(QColor("#ffd700"))
            painter.setPen(pen)
            brush = QBrush(QColor("#ffcc00"))
            painter.setBrush(brush)
            diameter = 20
            x = self.buttons_frame.geometry().x() + self.buttons_frame.width() - diameter - 8
            y = self.buttons_frame.geometry().y() - diameter // 2 + 2
            painter.drawEllipse(x, y, diameter, diameter)
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            painter.setPen(QColor("#1e1e1e"))
            painter.drawText(x + 6, y + 15, "!")

    def check_server_hash(self, client_hash):
        try:
            response = requests.get(f"{SERVER_URL}/api/check_build/{self.version}", timeout=5)
            server_hash = response.json().get("hash")
            if server_hash != client_hash:
                self.installRequested.emit()  # Автоматически запускает обновление
                return False
            return True
        except requests.RequestException:
            return False

    def set_install_state(self, state):
        self._install_state = state
        instance_dir = SERVER_INSTANCES_DIR if self.is_server else INSTANCES_DIR
        build_path = os.path.join(instance_dir, self.version)
        client_hash = calculate_folder_hash(build_path)

        if self.is_server and client_hash and not self.check_server_hash(client_hash):
            self._install_state = True  # Требуется обновление

        if self._install_state:
            self.play_btn.hide()
            self.settings_btn.hide()
            self.install_btn.show()
        else:
            self.play_btn.show()
            self.settings_btn.show()
            self.install_btn.hide()
        self.update()
        logger.info(f"Состояние установки для {self.version}: {self._install_state}")

    def get_bg_color(self):
        return self._bg_color

    def set_bg_color(self, color):
        self._bg_color = color
        current_style = self.styleSheet()
        new_style = current_style.replace(
            r"background-color: #[0-9a-fA-F]{6}",
            f"background-color: {color.name()}"
        ) if "background-color" in current_style else f"{current_style} QFrame#build_frame {{ background-color: {color.name()}; }}"
        self.setStyleSheet(new_style)

    bg_color = Property(QColor, get_bg_color, set_bg_color)