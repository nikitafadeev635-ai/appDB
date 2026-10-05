"""
Promo Sheets Client - Работа с Google Sheets для промокодов
Отдельный модуль, чтобы не трогать основной функционал штрафов/бонусов
"""
import os
from typing import Optional, Dict
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import (
    GOOGLE_SHEETS_CREDENTIALS,
    GOOGLE_SHEETS_ID,
    GOOGLE_PROMO_SHEETS_ID,
    GOOGLE_PROMO_SHEETS_WORKSHEET
)


class PromoSheetsClient:
    """Клиент для работы с Google Sheets для промокодов"""

    def __init__(self, sheet_id: Optional[str] = None, worksheet_name: Optional[str] = None):
        # Используем свой sheet_id для промокодов, либо дефолтный из конфига
        self.sheet_id = sheet_id or GOOGLE_PROMO_SHEETS_ID or GOOGLE_SHEETS_ID
        self.worksheet_name = worksheet_name or GOOGLE_PROMO_SHEETS_WORKSHEET
        self.credentials_file = GOOGLE_SHEETS_CREDENTIALS
        
        # Scope для Google Sheets API
        self.scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        self.client = None

    def _get_client(self):
        """Создаёт и возвращает авторизованный клиент"""
        if self.client is None:
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(f"Файл {self.credentials_file} не найден")
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, self.scope
            )
            self.client = gspread.authorize(creds)
        return self.client

    def _get_worksheet(self, worksheet_name: Optional[str] = None):
        """Получает лист из таблицы"""
        client = self._get_client()
        spreadsheet = client.open_by_key(self.sheet_id)
        
        target_ws = worksheet_name or self.worksheet_name
        if target_ws:
            return spreadsheet.worksheet(target_ws)
        else:
            return spreadsheet.sheet1  # Первый лист по умолчанию

    def read_promocodes_from_sheet(
        self,
        worksheet_name: Optional[str] = None,
        start_row: int = 2,
        column: str = "A"
    ) -> Dict:
        """
        Читает промокоды из Google Таблицы построчно.
        
        Данные берутся из одной колонки (по умолчанию A), начиная со строки start_row.
        Каждая ячейка содержит CSV-строку вида: QFACT-01, "BONUS", 1, 5
        """
        import csv
        import io
        
        try:
            ws = self._get_worksheet(worksheet_name)
            
            # Получаем все значения из нужной колонки
            range_str = f"{column}{start_row}:{column}"
            cells = ws.get(range_str)
            
            promocodes = []
            errors = []
            
            for idx, row_cells in enumerate(cells):
                row_number = start_row + idx
                cell_value = row_cells[0] if row_cells else ""
                
                # Пропускаем пустые ячейки
                if not cell_value or not str(cell_value).strip():
                    continue
                
                try:
                    # Парсим CSV-строку внутри ячейки
                    reader = csv.reader(io.StringIO(str(cell_value)), skipinitialspace=True)
                    parts = next(reader)
                    
                    # Очищаем от кавычек и пробелов
                    parts = [p.strip().strip('"').strip("'") for p in parts]
                    
                    if len(parts) < 3:
                        errors.append(f"Строка {row_number}: слишком мало полей ({len(parts)})")
                        continue
                    
                    code = parts[0]
                    value_type = parts[1].upper()
                    value_amount = float(parts[2].replace(",", "."))
                    amount = int(parts[3]) if len(parts) > 3 else 1
                    
                    if not code:
                        errors.append(f"Строка {row_number}: пустой код")
                        continue
                    
                    if value_type not in ["BONUS", "DISCOUNT", "DEPOSIT"]:
                        errors.append(f"Строка {row_number}: неверный тип '{value_type}'")
                        continue
                    
                    promocodes.append({
                        "code": code,
                        "value_type": value_type,
                        "value_amount": value_amount,
                        "amount": amount,
                        "row": row_number
                    })
                    
                except (StopIteration, ValueError, IndexError) as e:
                    errors.append(f"Строка {row_number}: ошибка парсинга ({str(e)})")
            
            return {
                "success": True,
                "promocodes": promocodes,
                "errors": errors,
                "total": len(promocodes)
            }
            
        except Exception as e:
            return {
                "success": False,
                "promocodes": [],
                "errors": [f"Ошибка чтения таблицы: {str(e)}"],
                "total": 0
            }

    def mark_cell_green(self, row: int, column: str = "A", worksheet_name: Optional[str] = None) -> bool:
        """Помечает ячейку зелёным цветом"""
        try:
            ws = self._get_worksheet(worksheet_name)
            cell_range = f"{column}{row}"
            
            ws.format(cell_range, {
                "backgroundColor": {
                    "red": 0.6,
                    "green": 0.9,
                    "blue": 0.6
                }
            })
            return True
            
        except Exception as e:
            print(f"Ошибка пометки ячейки {column}{row}: {e}")
            return False

    def test_connection(self) -> Dict:
        """Проверяет соединение с таблицей промокодов"""
        try:
            ws = self._get_worksheet()
            return {
                "success": True,
                "message": f"Подключено к таблице: {ws.title} (ID: {self.sheet_id})"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка подключения: {str(e)}"
            }