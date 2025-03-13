import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCES_DIR = os.path.join(BASE_DIR, "instances")
SERVER_INSTANCES_DIR = os.path.join(BASE_DIR, "server_instances")
SERVER_URL = "http://localhost:5000"

MODRINTH_STYLE = """
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial;
}
QMainWindow {
    background-color: #1e1e1e;
}
QScrollArea {
    border: none;
    background-color: #1e1e1e;
}
QFrame#build_frame {
    background-color: #252525;
    border-radius: 10px;
    margin: 5px;
    border: 1px solid #353535;
}
QFrame#buttons_frame {
    background-color: transparent;
    border-radius: 15px; /* Округлый блок с кнопками */
}
QLabel {
    background-color: transparent;
}
QPushButton {
    background-color: #00a86b;
    border: none;
    border-radius: 6px;
    padding: 2px 12px;
    color: white;
    font-weight: bold;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #00c77f;
}
QPushButton:pressed {
    background-color: #008c56;
}
QPushButton#install_btn {
    background-color: #ffcc00; /* Желтый цвет для кнопки "Установить" */
    color: #1e1e1e; /* Темный текст для контраста */
}
QPushButton#install_btn:hover {
    background-color: #ffd700; /* Более яркий желтый при наведении */
}
QPushButton#install_btn:pressed {
    background-color: #d4a700; /* Темнее при нажатии */
}
QLineEdit {
    background-color: #252525;
    border: 1px solid #353535;
    border-radius: 6px;
    padding: 6px;
    color: #e0e0e0;
}
QLineEdit:focus {
    border: 1px solid #00a86b;
}
QComboBox {
    background-color: #252525;
    border: 1px solid #353535;
    border-radius: 6px;
    padding: 6px;
    color: #e0e0e0;
}
QComboBox:hover {
    border: 1px solid #00a86b;
}
QCheckBox {
    color: #e0e0e0;
}
QScrollBar:vertical {
    background: #1e1e1e;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #4a4a4a;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #606060;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    background: #252525;
    color: #e0e0e0;
    padding: 8px 16px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #353535;
}
QTabBar::tab:hover {
    background: #404040;
}
QPushButton#logout_btn {
    background-color: #ff5555;
}
QPushButton#logout_btn:hover {
    background-color: #ff7777;
}
QPushButton#logout_btn:pressed {
    background-color: #dd3333;
}

QPushButton {
    background-color: #00a86b;
    border: none;
    border-radius: 6px;
    padding: 2px 12px;
    color: white;
    font-weight: bold;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #00c77f;
}
QPushButton:pressed {
    background-color: #008c56;
}
QPushButton#install_btn {
    background-color: #ffcc00;
    color: #1e1e1e;
}
QPushButton#install_btn:hover {
    background-color: #ffd700;
}
QPushButton#install_btn:pressed {
    background-color: #d4a700;
}
"""