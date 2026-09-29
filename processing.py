"""
Processing Module - Обработка, фильтрация и сортировка данных
"""
import pandas as pd
from typing import Optional


class DataProcessor:
    """Процессор для обработки данных таблиц"""

    def __init__(self):
        self.current_data: Optional[pd.DataFrame] = None
        self.original_data: Optional[pd.DataFrame] = None

    def load_data(self, df: pd.DataFrame):
        self.original_data = df.copy()
        self.current_data = df.copy()

    def get_data(self) -> pd.DataFrame:
        return self.current_data if self.current_data is not None else pd.DataFrame()

    def reset_filters(self):
        if self.original_data is not None:
            self.current_data = self.original_data.copy()

    def filter_by_range(self, column: str, min_val: Optional[float], max_val: Optional[float]) -> pd.DataFrame:
        if self.current_data is None or self.current_data.empty:
            return pd.DataFrame()
        if column not in self.current_data.columns:
            return self.current_data
        if min_val is not None:
            self.current_data = self.current_data[self.current_data[column] >= min_val]
        if max_val is not None:
            self.current_data = self.current_data[self.current_data[column] <= max_val]
        return self.current_data

    def get_negative_stock_items(self) -> pd.DataFrame:
        if self.current_data is None or self.current_data.empty:
            return pd.DataFrame()
        if "stock" in self.current_data.columns:
            return self.current_data[self.current_data["stock"] < 0]
        return pd.DataFrame()

    def export_to_csv(self, file_path: str) -> bool:
        try:
            if self.current_data is not None:
                self.current_data.to_csv(file_path, index=False, encoding="utf-8-sig")
                return True
        except Exception as e:
            print(f"Ошибка экспорта в CSV: {e}")
        return False

    def export_to_excel(self, file_path: str) -> bool:
        try:
            if self.current_data is not None:
                self.current_data.to_excel(file_path, index=False, engine="openpyxl")
                return True
        except Exception as e:
            print(f"Ошибка экспорта в Excel: {e}")
        return False