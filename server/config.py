"""
Config Module - Конфигурация для PromoMonitor Daemon
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# === MySQL Database ===
DB_HOST = os.getenv("DB_HOST", "vh454.timeweb.ru")
DB_USER = os.getenv("DB_USER", "cj25907_cybermg")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "cj25907_cybermg")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

# === SmartShell Account 2 (для мониторинга событий и синхронизации) ===
# СТАРЫЙ эндпоинт — для EventList и логина
SMARTSHELL2_GRAPHQL_URL = os.getenv("SMARTSHELL2_GRAPHQL_URL", "https://billing.smartshell.gg/api/graphql")
# V2 эндпоинт — для PromoCodesListV2, UpdatePromoCodeV2, DeletePromoCodeV2
SMARTSHELL2_V2_GRAPHQL_URL = os.getenv("SMARTSHELL2_V2_GRAPHQL_URL", "https://billing.smartshell.gg/api/v2/graphql")
SMARTSHELL2_LOGIN = os.getenv("SMARTSHELL2_LOGIN", "")
SMARTSHELL2_PASSWORD = os.getenv("SMARTSHELL2_PASSWORD", "")

# === Точки SmartShell ===
SMARTSHELL_WAREHOUSE_IDS = {
    "Русская": 1598,
    "Сахалинская": 3241,
    "Трамвайная": 2610,
    "Светланская": 7879,
    "Ульяновская": 4532,
    "Калинина": 10178
}