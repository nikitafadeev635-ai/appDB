"""
Google Sheets Client Module - Обновление таблицы учёта минусов
Работает напрямую через gspread (локально, без VPS)
"""
import os
from pathlib import Path
from typing import Dict, Optional
import gspread
from google.oauth2.service_account import Credentials

from config import BASE_DIR, GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_WORKSHEET


# Маппинг колонок (индексы с 1, как в Google Sheets)
COLUMN_MAP = {
    "Имя": 1,
    "Точка": 2,
    "Тег": 3,
    "Штрафы": 4,
    "Минуса": 5,
    "Спорный": 6,
    "Склад": 7,
    "СуммЧел": 8,
    "Учтено с": 9,
    "Учтено по": 10,
    "Состояние": 11,
    "Оценка работы(10)": 12,
    "Премия": 13,
    "Лимит на игру": 14,
    "Зачет: Оценка,проблемы": 15,
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetsClient:
    """Клиент для работы с Google Sheets"""

    def __init__(self):
        self.credentials_path = BASE_DIR / GOOGLE_SHEETS_CREDENTIALS
        self.sheet_id = GOOGLE_SHEETS_ID
        self.worksheet_name = GOOGLE_SHEETS_WORKSHEET
        self._client = None
        self._worksheet = None

    # ============================================================
    #  ПОДКЛЮЧЕНИЕ
    # ============================================================
    def _get_client(self):
        """Получает gspread-клиент (ленивая инициализация)"""
        if self._client is None:
            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    f"Файл ключей не найден: {self.credentials_path}\n"
                    f"Скачайте JSON-ключ из Google Cloud Console"
                )
            
            creds = Credentials.from_service_account_file(
                str(self.credentials_path), scopes=SCOPES
            )
            self._client = gspread.authorize(creds)
        return self._client

    def _get_worksheet(self):
        """Получает worksheet (ленивая инициализация)"""
        if self._worksheet is None:
            if not self.sheet_id:
                raise ValueError(
                    "GOOGLE_SHEETS_ID не указан в .env!\n"
                    "Добавьте строку: GOOGLE_SHEETS_ID=ваш_id_таблицы"
                )
            
            client = self._get_client()
            spreadsheet = client.open_by_key(self.sheet_id)
            self._worksheet = spreadsheet.worksheet(self.worksheet_name)
        return self._worksheet

    # ============================================================
    #  ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================
    def _safe_float(self, value) -> float:
        """Безопасно преобразует значение в float"""
        if value is None or value == "":
            return 0.0
        try:
            return float(str(value).replace(",", ".").replace(" ", ""))
        except (ValueError, TypeError):
            return 0.0

    def find_admin_row(self, admin_name: str) -> Optional[int]:
        """
        Ищет строку администратора по имени.
        Возвращает номер строки (1-based) или None если не найден.
        """
        ws = self._get_worksheet()
        name_col = COLUMN_MAP["Имя"]
        
        # Читаем колонку "Имя"
        names = ws.col_values(name_col)
        
        for idx, name in enumerate(names, start=1):
            if idx == 1:  # Пропускаем заголовок
                continue
            if name and name.strip().lower() == admin_name.strip().lower():
                return idx
        
        return None

    # ============================================================
    #  ОБНОВЛЕНИЕ ЗНАЧЕНИЙ
    # ============================================================
    def decrease_values(
        self,
        admin_name: str,
        minus_decrease: float,
        disputed_decrease: float,
    ) -> Dict:
        """
        Уменьшает поля "Минуса" и "Спорный" для администратора.
        
        Логика:
        - "Спорный" уменьшается ВСЕГДА на сумму обработанной записи
        - "Минуса" уменьшается ТОЛЬКО если причина оправдана
        
        Args:
            admin_name: Имя администратора
            minus_decrease: Насколько уменьшить "Минуса" (0 если не оправдано)
            disputed_decrease: Насколько уменьшить "Спорный"
        
        Returns:
            {
                "success": bool,
                "message": str,
                "row": int,
                "old_minus": float,
                "new_minus": float,
                "old_disputed": float,
                "new_disputed": float,
            }
        """
        try:
            row_num = self.find_admin_row(admin_name)
            if row_num is None:
                return {
                    "success": False,
                    "message": f"Администратор '{admin_name}' не найден в таблице",
                    "row": 0,
                    "old_minus": 0,
                    "new_minus": 0,
                    "old_disputed": 0,
                    "new_disputed": 0,
                }

            ws = self._get_worksheet()
            minus_col = COLUMN_MAP["Минуса"]
            disputed_col = COLUMN_MAP["Спорный"]

            # Читаем текущие значения
            current_minus = self._safe_float(ws.cell(row_num, minus_col).value)
            current_disputed = self._safe_float(ws.cell(row_num, disputed_col).value)

            # Вычисляем новые значения (не уходим в минус)
            new_minus = max(0.0, current_minus - minus_decrease)
            new_disputed = max(0.0, current_disputed - disputed_decrease)

            # Обновляем ячейки
            ws.update_cell(row_num, minus_col, new_minus)
            ws.update_cell(row_num, disputed_col, new_disputed)

            print(
                f"[GoogleSheets] ✓ Обновлена строка '{admin_name}' (row {row_num}): "
                f"Минуса {current_minus} → {new_minus}, "
                f"Спорный {current_disputed} → {new_disputed}"
            )

            return {
                "success": True,
                "message": (
                    f"Минуса: {current_minus:.2f} → {new_minus:.2f}, "
                    f"Спорный: {current_disputed:.2f} → {new_disputed:.2f}"
                ),
                "row": row_num,
                "old_minus": current_minus,
                "new_minus": new_minus,
                "old_disputed": current_disputed,
                "new_disputed": new_disputed,
            }

        except FileNotFoundError as e:
            return {
                "success": False,
                "message": str(e),
                "row": 0,
                "old_minus": 0,
                "new_minus": 0,
                "old_disputed": 0,
                "new_disputed": 0,
            }
        except Exception as e:
            print(f"[GoogleSheets] ✗ Ошибка: {e}")
            return {
                "success": False,
                "message": f"Ошибка обновления: {e}",
                "row": 0,
                "old_minus": 0,
                "new_minus": 0,
                "old_disputed": 0,
                "new_disputed": 0,
            }

    def test_connection(self) -> Dict:
        """Проверяет подключение к таблице"""
        try:
            ws = self._get_worksheet()
            title = ws.title
            return {
                "success": True,
                "message": f"Подключено к таблице: '{title}'",
                "worksheet": title,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка подключения: {e}",
                "worksheet": None,
            }
