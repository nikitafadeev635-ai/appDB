"""
Data Module - Работа с базой данных MySQL через PyMySQL
"""
import pymysql
from typing import List, Dict, Optional
from config import DB_CONFIG
import pandas as pd


class DatabaseManager:
    """Менеджер подключения и запрос к БД"""

    def __init__(self):
        self.connection = None
        self.connect()

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
            print("✅ Подключено к базе данных")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к БД: {e}")
            return False

    def disconnect(self):
        """Отключение от базы данных"""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            print("✅ Отключено от базы данных")

    def reconnect(self) -> bool:
        """Переподключение"""
        self.disconnect()
        return self.connect()

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Выполнение SELECT запроса"""
        try:
            if not self.connection or not self.connection.open:
                self.connect()
            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
            self.reconnect()
            return []

    def execute_update(self, query: str, params: tuple = None) -> bool:
        """Выполнение UPDATE/INSERT запроса"""
        try:
            if not self.connection or not self.connection.open:
                self.connect()
            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                self.connection.commit()
                return True
        except Exception as e:
            print(f"❌ Ошибка обновления: {e}")
            if self.connection:
                self.connection.rollback()
            return False

    # === ТОВАРЫ ===

    def get_all_products(self, warehouse: str = None, supplier: str = None,
                        min_stock: int = None, max_stock: int = None,
                        search_text: str = None) -> pd.DataFrame:
        """Получение всех товаров с фильтрами"""
        query = """
            SELECT
                p.id,
                w.name as warehouse,
                p.name,
                p.supplier,
                p.stock,
                p.fact_end_month,
                p.created_at,
                p.updated_at
            FROM products p
            JOIN warehouses w ON p.warehouse_id = w.id
            WHERE 1=1
        """
        params = []

        if warehouse and warehouse != "Все":
            query += " AND w.name = %s"
            params.append(warehouse)
        if supplier and supplier != "Все":
            query += " AND p.supplier = %s"
            params.append(supplier)
        if min_stock is not None:
            query += " AND p.stock >= %s"
            params.append(min_stock)
        if max_stock is not None:
            query += " AND p.stock <= %s"
            params.append(max_stock)
        if search_text and search_text.strip():
            query += " AND (p.name LIKE %s OR p.supplier LIKE %s)"
            params.extend([f"%{search_text}%", f"%{search_text}%"])

        query += " ORDER BY w.name, p.name"
        results = self.execute_query(query, tuple(params))
        return pd.DataFrame(results)

    def get_unique_suppliers(self) -> List[str]:
        """Список уникальных поставщиков"""
        query = "SELECT DISTINCT supplier FROM products WHERE supplier IS NOT NULL ORDER BY supplier"
        results = self.execute_query(query)
        return ["Все"] + [row["supplier"] for row in results if row["supplier"]]

    def update_product_stock(self, product_id: int, new_stock: int) -> bool:
        """Обновление остатка товара"""
        query = "UPDATE products SET stock = %s WHERE id = %s"
        return self.execute_update(query, (new_stock, product_id))

    def update_product_supplier(self, product_id: int, supplier: str) -> bool:
        """Обновление поставщика товара"""
        query = "UPDATE products SET supplier = %s WHERE id = %s"
        return self.execute_update(query, (supplier, product_id))

    def add_product_to_warehouses(self, product_name: str, warehouse_ids: list,
                                   supplier: str = None, initial_stock: int = 0) -> dict:
        """Добавляет товар на несколько точек сразу"""
        result = {"success": [], "skipped": [], "errors": []}

        if not warehouse_ids:
            result["errors"].append("Не выбрано ни одной точки")
            return result
        if not product_name or not product_name.strip():
            result["errors"].append("Название товара не может быть пустым")
            return result

        try:
            if not self.connection or not self.connection.open:
                self.connect()

            with self.connection.cursor() as cursor:
                for wh_id in warehouse_ids:
                    cursor.execute("SELECT name FROM warehouses WHERE id = %s", (wh_id,))
                    wh_row = cursor.fetchone()
                    if not wh_row:
                        result["errors"].append(f"Точка с ID {wh_id} не найдена")
                        continue

                    wh_name = wh_row["name"] if isinstance(wh_row, dict) else wh_row[0]

                    # Проверяем дубликат
                    cursor.execute("""
                        SELECT id FROM products
                        WHERE warehouse_id = %s AND name = %s
                    """, (wh_id, product_name.strip()))

                    if cursor.fetchone():
                        result["skipped"].append(wh_name)
                        continue

                    try:
                        cursor.execute("""
                            INSERT INTO products (warehouse_id, name, supplier, stock)
                            VALUES (%s, %s, %s, %s)
                        """, (wh_id, product_name.strip(), supplier or None, initial_stock))
                        result["success"].append(wh_name)
                    except Exception as e:
                        result["errors"].append(f"{wh_name}: {str(e)}")

                self.connection.commit()
        except Exception as e:
            result["errors"].append(f"Ошибка БД: {str(e)}")
            if self.connection:
                self.connection.rollback()

        return result

    # === ОПЕРАЦИИ ===

    def get_operations(self, warehouse: str = None, operation_type: str = None,
                      date_from: str = None, date_to: str = None,
                      search_text: str = None) -> pd.DataFrame:
        """Журнал операций"""
        query = """
            SELECT
                id, operation_date, warehouse_name, product_name, quantity,
                operation_type, user_id, username, full_name, comment, created_at
            FROM operations_log
            WHERE 1=1
        """
        params = []

        if warehouse and warehouse != "Все":
            query += " AND warehouse_name = %s"
            params.append(warehouse)
        if operation_type and operation_type != "Все":
            query += " AND operation_type = %s"
            params.append(operation_type)
        if date_from:
            query += " AND operation_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND operation_date <= %s"
            params.append(date_to)
        if search_text and search_text.strip():
            query += " AND (product_name LIKE %s OR comment LIKE %s OR username LIKE %s)"
            params.extend([f"%{search_text}%"] * 3)

        query += " ORDER BY created_at DESC"
        results = self.execute_query(query, tuple(params))
        return pd.DataFrame(results)

    def get_penalties(self) -> pd.DataFrame:
        """Список штрафов"""
        query = "SELECT * FROM penalties ORDER BY created_at DESC"
        return pd.DataFrame(self.execute_query(query))

    def get_balance_corrections(self) -> pd.DataFrame:
        """Корректировки баланса"""
        query = "SELECT * FROM balance_corrections ORDER BY created_at DESC"
        return pd.DataFrame(self.execute_query(query))

    def get_processed_factures(self, warehouse: str = None, 
                            date_from: str = None, date_to: str = None,
                            search_text: str = None) -> pd.DataFrame:
        """Обработанные фактуры из СБИС (таблица processed_factures)"""
        query = """
            SELECT
                id,
                warehouse_name,
                document_number,
                document_date,
                processed_at
            FROM processed_factures
            WHERE 1=1
        """
        params = []

        if warehouse and warehouse != "Все":
            query += " AND warehouse_name = %s"
            params.append(warehouse)
        if date_from:
            query += " AND processed_at >= %s"
            params.append(date_from)
        if date_to:
            query += " AND processed_at <= %s"
            params.append(date_to)
        if search_text and search_text.strip():
            query += " AND (document_number LIKE %s OR warehouse_name LIKE %s)"
            params.extend([f"%{search_text}%", f"%{search_text}%"])

        query += " ORDER BY processed_at DESC"
        results = self.execute_query(query, tuple(params))
        return pd.DataFrame(results)

        # Для обратной совместимости оставляем старый метод
    def get_processed_invoices(self, date_from: str = None, 
                            date_to: str = None,
                            search_text: str = None) -> pd.DataFrame:
        """
        Получение переданных фактур из таблицы processed_invoices.
        
        Таблица содержит:
        - id: первичный ключ
        - invoice_number: номер фактуры
        - processed_at: дата/время обработки
        """
        query = """
            SELECT
                id,
                invoice_number,
                processed_at
            FROM processed_invoices
            WHERE 1=1
        """
        params = []
        
        if date_from:
            query += " AND processed_at >= %s"
            params.append(date_from)
        if date_to:
            query += " AND processed_at <= %s"
            params.append(date_to)
        if search_text and search_text.strip():
            query += " AND invoice_number LIKE %s"
            params.append(f"%{search_text}%")
        
        query += " ORDER BY processed_at DESC"
        
        results = self.execute_query(query, tuple(params))
        print(f"[Invoices] Прочитано записей: {len(results)}")
        
        return pd.DataFrame(results)
    def get_missing_smartshell_items(self) -> pd.DataFrame:
        """Товары без маппинга SmartShell"""
        query = "SELECT * FROM missing_smartshell_items ORDER BY created_at DESC"
        return pd.DataFrame(self.execute_query(query))

    # === СТАТИСТИКА ===

    def get_warehouse_stats(self) -> pd.DataFrame:
        """Статистика по точкам"""
        query = """
            SELECT
                w.name as warehouse,
                COUNT(p.id) as product_count,
                SUM(CASE WHEN p.stock < 0 THEN 1 ELSE 0 END) as negative_stock_count,
                SUM(CASE WHEN p.stock = 0 THEN 1 ELSE 0 END) as zero_stock_count,
                SUM(CASE WHEN p.stock > 0 THEN 1 ELSE 0 END) as positive_stock_count,
                ROUND(AVG(p.stock), 2) as avg_stock
            FROM warehouses w
            LEFT JOIN products p ON w.id = p.warehouse_id
            GROUP BY w.id, w.name
            ORDER BY w.name
        """
        return pd.DataFrame(self.execute_query(query))

    def get_supplier_stats(self) -> pd.DataFrame:
        """Статистика по поставщикам"""
        query = """
            SELECT
                supplier,
                COUNT(*) as product_count,
                COUNT(DISTINCT warehouse_id) as warehouse_count,
                SUM(CASE WHEN stock < 0 THEN 1 ELSE 0 END) as negative_items,
                ROUND(AVG(stock), 2) as avg_stock
            FROM products
            WHERE supplier IS NOT NULL
            GROUP BY supplier
            ORDER BY product_count DESC
        """
        return pd.DataFrame(self.execute_query(query))