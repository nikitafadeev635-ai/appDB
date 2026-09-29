"""
RefState Repository Module - Работа с таблицей refStateDetailed
Модуль для обработки расхождений: получение записей, пометка, удаление, бэкап
"""
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import pymysql

from config import DB_CONFIG, BASE_DIR


class RefStateRepository:
    """Репозиторий для работы с таблицей refStateDetailed"""

    def __init__(self):
        self.connection = None
        self.backups_dir = BASE_DIR / "backups"
        self.backups_dir.mkdir(exist_ok=True)

    # ============================================================
    #  ПОДКЛЮЧЕНИЕ
    # ============================================================
    def connect(self) -> bool:
        """Подключение к базе данных"""
        try:
            self.connection = pymysql.connect(
                host=DB_CONFIG["host"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                port=int(DB_CONFIG["port"]),
                charset=DB_CONFIG.get("charset", "utf8mb4"),
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10
            )
            return True
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка подключения к БД: {e}")
            return False

    def disconnect(self):
        """Отключение от базы данных"""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass

    def _ensure_connection(self):
        """Гарантирует наличие активного подключения"""
        if not self.connection or not self.connection.open:
            self.connect()

    # ============================================================
    #  ПОЛУЧЕНИЕ ДАННЫХ
    # ============================================================
    def get_administrators_summary(self) -> List[Dict]:
        """
        Получает список администраторов с необработанными записями.
        
        Returns:
            [
                {
                    "administrator": "Иванов Иван",
                    "records_count": 5,
                    "total_value": 1250.00,
                    "last_created": datetime(...)
                },
                ...
            ]
        """
        self._ensure_connection()
        query = """
            SELECT 
                administrator,
                COUNT(*) as records_count,
                SUM(value) as total_value,
                MAX(created_at) as last_created
            FROM refStateDetailed
            GROUP BY administrator
            ORDER BY last_created DESC, administrator ASC
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
                # Преобразуем Decimal в float для удобства
                for row in results:
                    if row["total_value"] is not None:
                        row["total_value"] = float(row["total_value"])
                
                return results
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка get_administrators_summary: {e}")
            return []

    def get_records_by_admin(self, administrator: str) -> List[Dict]:
        """
        Получает все записи конкретного администратора.
        
        Args:
            administrator: Имя администратора
            
        Returns:
            [
                {
                    "id": 6,
                    "general_id": 6,
                    "created_at": datetime(...),
                    "administrator": "Александрова Александра",
                    "product_title": "Бургер",
                    "product_id": 0,
                    "reference": "Lost1",
                    "quantity": 1,
                    "value": Decimal('370.00'),
                    "reason": "Товар украден"
                },
                ...
            ]
        """
        self._ensure_connection()
        query = """
            SELECT 
                id, general_id, created_at, administrator,
                product_title, product_id, reference,
                quantity, value, reason
            FROM refStateDetailed
            WHERE administrator = %s
            ORDER BY created_at DESC, id ASC
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (administrator,))
                results = cursor.fetchall()
                
                # Преобразуем Decimal в float
                for row in results:
                    if row["value"] is not None:
                        row["value"] = float(row["value"])
                
                return results
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка get_records_by_admin: {e}")
            return []

    def get_record_by_id(self, record_id: int) -> Optional[Dict]:
        """Получает одну запись по ID"""
        self._ensure_connection()
        query = "SELECT * FROM refStateDetailed WHERE id = %s"
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (record_id,))
                row = cursor.fetchone()
                if row and row["value"] is not None:
                    row["value"] = float(row["value"])
                return row
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка get_record_by_id: {e}")
            return None

    # ============================================================
    #  УДАЛЕНИЕ (после обработки)
    # ============================================================
    def delete_record(self, record_id: int) -> bool:
        """
        Удаляет запись после обработки.
        
        Args:
            record_id: ID записи для удаления
            
        Returns:
            True если успешно удалено
        """
        self._ensure_connection()
        query = "DELETE FROM refStateDetailed WHERE id = %s"
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (record_id,))
                self.connection.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка delete_record: {e}")
            if self.connection:
                self.connection.rollback()
            return False

    def delete_records_batch(self, record_ids: List[int]) -> Dict:
        """
        Пакетное удаление записей.
        
        Returns:
            {"deleted": int, "errors": int}
        """
        self._ensure_connection()
        deleted = 0
        errors = 0
        
        try:
            with self.connection.cursor() as cursor:
                for record_id in record_ids:
                    try:
                        cursor.execute(
                            "DELETE FROM refStateDetailed WHERE id = %s",
                            (record_id,)
                        )
                        deleted += 1
                    except Exception:
                        errors += 1
                
                self.connection.commit()
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка delete_records_batch: {e}")
            if self.connection:
                self.connection.rollback()
        
        return {"deleted": deleted, "errors": errors}

    # ============================================================
    #  БЭКАП ТАБЛИЦЫ
    # ============================================================
    def backup_table(self) -> Dict:
        """
        Создаёт дамп таблицы refStateDetailed в SQL-файл.
        Файл сохраняется в папку backups/ с меткой времени.
        
        Returns:
            {
                "success": bool,
                "file_path": str,
                "records_count": int,
                "message": str
            }
        """
        self._ensure_connection()
        
        try:
            # Получаем все данные
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT * FROM refStateDetailed ORDER BY id")
                records = cursor.fetchall()
            
            # Формируем имя файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"refStateDetailed_backup_{timestamp}.sql"
            file_path = self.backups_dir / filename
            
            # Генерируем SQL-файл
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"-- Backup of refStateDetailed\n")
                f.write(f"-- Created at: {datetime.now().isoformat()}\n")
                f.write(f"-- Records count: {len(records)}\n\n")
                
                if not records:
                    f.write("-- No records to backup\n")
                    return {
                        "success": True,
                        "file_path": str(file_path),
                        "records_count": 0,
                        "message": "Бэкап создан (таблица пуста)"
                    }
                
                # Получаем список колонок из первой записи
                columns = list(records[0].keys())
                columns_str = ", ".join(f"`{col}`" for col in columns)
                
                # Генерируем INSERT операторы
                f.write("-- Данные для восстановления:\n")
                f.write("-- DELETE FROM refStateDetailed;  -- раскомментируйте для полного восстановления\n")
                f.write("-- Затем выполните INSERT ниже\n\n")
                
                for record in records:
                    values = []
                    for col in columns:
                        value = record[col]
                        if value is None:
                            values.append("NULL")
                        elif isinstance(value, (int, float)):
                            values.append(str(value))
                        elif isinstance(value, datetime):
                            values.append(f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'")
                        else:
                            # Экранируем строки
                            escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
                            values.append(f"'{escaped}'")
                    
                    values_str = ", ".join(values)
                    f.write(f"INSERT INTO refStateDetailed ({columns_str}) VALUES ({values_str});\n")
            
            return {
                "success": True,
                "file_path": str(file_path),
                "records_count": len(records),
                "message": f"Бэкап создан: {len(records)} записей"
            }
        
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка backup_table: {e}")
            return {
                "success": False,
                "file_path": "",
                "records_count": 0,
                "message": f"Ошибка бэкапа: {e}"
            }

    def get_backups_list(self) -> List[Dict]:
        """Получает список существующих бэкапов"""
        backups = []
        try:
            for file in sorted(self.backups_dir.glob("*.sql"), reverse=True):
                stat = file.stat()
                backups.append({
                    "filename": file.name,
                    "file_path": str(file),
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime)
                })
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка get_backups_list: {e}")
        return backups

    # ============================================================
    #  СТАТИСТИКА
    # ============================================================
    def get_total_stats(self) -> Dict:
        """Общая статистика по необработанным записям"""
        self._ensure_connection()
        query = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT administrator) as total_admins,
                SUM(value) as total_value
            FROM refStateDetailed
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()
                if row and row["total_value"] is not None:
                    row["total_value"] = float(row["total_value"])
                return row or {"total_records": 0, "total_admins": 0, "total_value": 0.0}
        except Exception as e:
            print(f"[RefStateRepo] ❌ Ошибка get_total_stats: {e}")
            return {"total_records": 0, "total_admins": 0, "total_value": 0.0}