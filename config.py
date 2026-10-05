"""
Config Module - Конфигурация и константы приложения
Загружает настройки из .env файла
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# === MySQL Database ===
DB_HOST = os.getenv("DB_HOST", "vh454.timeweb.ru")
DB_USER = os.getenv("DB_USER", "cj25907_cybermg")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "cj25907_cybermg")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

# === SmartShell ===
# === SmartShell Account 1 (Основной, для интерфейса и создания товаров/промокодов) ===
SMARTSHELL_GRAPHQL_URL = os.getenv("SMARTSHELL_GRAPHQL_URL", "https://billing.smartshell.gg/api/graphql")
SMARTSHELL_V2_GRAPHQL_URL = "https://billing.smartshell.gg/api/v2/graphql"  # V2 URL одинаковый для всех
SMARTSHELL_LOGIN = os.getenv("SMARTSHELL_LOGIN", "")
SMARTSHELL_PASSWORD = os.getenv("SMARTSHELL_PASSWORD", "")

# === SmartShell Account 2 (Для фонового мониторинга событий и синхронизации) ===
# Использует тот же старый эндпоинт для EventList и тот же V2 для PromoCodesListV2 / UpdatePromoCodeV2
SMARTSHELL2_GRAPHQL_URL = os.getenv("SMARTSHELL2_GRAPHQL_URL", "https://billing.smartshell.gg/api/graphql")
SMARTSHELL2_V2_GRAPHQL_URL = "https://billing.smartshell.gg/api/v2/graphql"
SMARTSHELL2_LOGIN = os.getenv("SMARTSHELL2_LOGIN", "")
SMARTSHELL2_PASSWORD = os.getenv("SMARTSHELL2_PASSWORD", "")
SMARTSHELL_WAREHOUSE_IDS = {
    "Русская": 1598,
    "Сахалинская": 3241,
    "Трамвайная": 2610,
    "Светланская": 7879,
    "Ульяновская": 4532,
    "Калинина": 10178
}

# === ПУТИ ===
ASSETS_DIR = BASE_DIR / "assets"
RESOURCES_DIR = BASE_DIR / "resources"
CONFIG_DIR = BASE_DIR / "config"

# === БАЗА ДАННЫХ ===
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "vh454.timeweb.ru"),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", ""),
    "port": int(os.getenv("DB_PORT", 3306)),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "collation": "utf8mb4_unicode_ci"
}

# === Google Sheets ===
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "credentials.json")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
GOOGLE_SHEETS_WORKSHEET = os.getenv("GOOGLE_SHEETS_WORKSHEET", "Штрафы")

# === Promo Sheets (промокоды) ===
# Если промокоды в той же таблице - оставь GOOGLE_PROMO_SHEETS_ID пустым (будет использован GOOGLE_SHEETS_ID)
# Если в отдельной таблице - укажи её ID
GOOGLE_PROMO_SHEETS_ID = os.getenv("GOOGLE_PROMO_SHEETS_ID", "")
GOOGLE_PROMO_SHEETS_WORKSHEET = os.getenv("GOOGLE_PROMO_SHEETS_WORKSHEET", "Промокоды")

# === ТОЧКИ СКЛАДА ===
WAREHOUSES = [
    "Русская",
    "Сахалинская",
    "Трамвайная",
    "Светланская",
    "Ульяновская",
    "Калинина"
]

# === ОПЕРАЦИИ ===
OPERATIONS = [
    "взял",
    "пришёл",
    "взял_периферию",
    "пришла_периферию",
    "убрал_периферию",
    "изменение_штрихкода"
]

# === НАСТРОЙКИ UI ===
WINDOW_TITLE = "QFACT - Система учёта склада"
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
TABLE_ROW_HEIGHT = 40

# === ТЁМНАЯ ТЕМА ===
DARK_THEME = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #1e1e2e;
}
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 16px;
    color: #cdd6f4;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton:disabled {
    background-color: #26283a;
    color: #6c7086;
}
QTableWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 4px;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}
QTableWidget::item {
    padding: 8px;
}
QHeaderView::section {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 8px;
    font-weight: bold;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 8px;
    color: #cdd6f4;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #89b4fa;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #cdd6f4;
    margin-right: 10px;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #181825;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #313244;
    color: #cdd6f4;
    padding: 10px 20px;
    border: 1px solid #45475a;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #181825;
    border-bottom: 2px solid #89b4fa;
}
QTabBar::tab:hover {
    background-color: #45475a;
}
QLabel {
    color: #cdd6f4;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    color: #cdd6f4;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #89b4fa;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #181825;
    width: 12px;
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 6px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}
QStatusBar {
    background-color: #313244;
    color: #cdd6f4;
    border-top: 1px solid #45475a;
}
QMenuBar {
    background-color: #313244;
    color: #cdd6f4;
}
QMenuBar::item:selected {
    background-color: #45475a;
}
QMenu {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
}
QMenu::item:selected {
    background-color: #45475a;
}
QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QDialogButtonBox QPushButton {
    min-width: 80px;
}
"""