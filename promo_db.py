"""
Promo DB Module - Работа с MySQL для отслеживания промокодов
Две таблицы:
  1. promo_codes — общий контроль (код, лимит, использовано)
  2. promo_usage_by_point — аналитика по точкам
"""
import pymysql
import os
from typing import Optional, Dict, List, Tuple
from datetime import datetime

# Читаем параметры БД из переменных окружения
DB_HOST = os.getenv("DB_HOST", "vh454.timeweb.ru")
DB_USER = os.getenv("DB_USER", "cj25907_cybermg")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "cj25907_cybermg")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")


def get_connection():
    """Создаёт подключение к MySQL"""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        charset=DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor
    )


def init_promo_tables():
    """Создаёт таблицы для отслеживания промокодов (если их нет)"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Таблица 1: общий контроль промокодов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(255) NOT NULL UNIQUE,
                    total_amount INT NOT NULL,
                    used_count INT DEFAULT 0,
                    is_deleted BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP NULL,
                    INDEX idx_code (code),
                    INDEX idx_is_deleted (is_deleted)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Таблица 2: использования по точкам
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS promo_usage_by_point (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    point_name VARCHAR(255) NOT NULL,
                    promo_code VARCHAR(255) NOT NULL,
                    used_count INT DEFAULT 0,
                    last_used_at TIMESTAMP NULL,
                    UNIQUE KEY uk_point_code (point_name, promo_code),
                    INDEX idx_promo_code (promo_code),
                    FOREIGN KEY (promo_code) REFERENCES promo_codes(code) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Таблица 3: дедупликация событий (чтобы не обрабатывать одно событие дважды)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS promo_events_processed (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    event_key VARCHAR(500) NOT NULL UNIQUE,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_event_key (event_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        
        conn.commit()
        print("[PromoDB] ✅ Таблицы созданы/проверены")
    except Exception as e:
        print(f"[PromoDB] ❌ Ошибка создания таблиц: {e}")
    finally:
        conn.close()


def register_promo_code(code: str, total_amount: int) -> bool:
    """
    Регистрирует промокод в БД при его создании.
    С подробным логированием для диагностики.
    """
    print(f"[PromoDB] 🔍 Попытка регистрации: code='{code}', amount={total_amount}")
    
    try:
        conn = get_connection()
        print(f"[PromoDB] ✅ Подключение к БД установлено: {DB_HOST}/{DB_NAME}")
    except Exception as e:
        print(f"[PromoDB] ❌ Ошибка подключения к БД: {e}")
        return False
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO promo_codes (code, total_amount, used_count, is_deleted)
                VALUES (%s, %s, 0, FALSE)
                ON DUPLICATE KEY UPDATE 
                    total_amount = VALUES(total_amount),
                    used_count = 0,
                    is_deleted = FALSE,
                    deleted_at = NULL
            """, (code, total_amount))
            
            affected_rows = cursor.rowcount
            conn.commit()
            
            print(f"[PromoDB] ✅ Промокод '{code}' зарегистрирован (лимит: {total_amount}, affected: {affected_rows})")
            return True
    except pymysql.err.ProgrammingError as e:
        print(f"[PromoDB] ❌ Ошибка SQL (таблица не существует?): {e}")
        return False
    except Exception as e:
        print(f"[PromoDB] ❌ Ошибка регистрации промокода '{code}': {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def is_event_processed(event_key: str) -> bool:
    """Проверяет, было ли событие уже обработано (дедупликация)"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM promo_events_processed WHERE event_key = %s",
                (event_key,)
            )
            return cursor.fetchone() is not None
    except Exception as e:
        print(f"[PromoDB] ❌ Ошибка проверки события: {e}")
        return False
    finally:
        conn.close()


def mark_event_processed(event_key: str):
    """Помечает событие как обработанное"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT IGNORE INTO promo_events_processed (event_key) VALUES (%s)",
                (event_key,)
            )
        conn.commit()
    except Exception as e:
        print(f"[PromoDB] ❌ Ошибка пометки события: {e}")
    finally:
        conn.close()


def record_promo_usage(code: str, point_name: str) -> Optional[Dict]:
    """
    Записывает использование промокода.
    Возвращает {"used_count": int, "total_amount": int, "is_exhausted": bool} или None.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Увеличиваем общий счётчик (атомарно)
            cursor.execute("""
                UPDATE promo_codes 
                SET used_count = used_count + 1 
                WHERE code = %s AND is_deleted = FALSE
            """, (code,))
            
            if cursor.rowcount == 0:
                print(f"[PromoDB] ⚠️ Промокод '{code}' не найден или уже удалён")
                return None
            
            # 2. Увеличиваем счётчик для конкретной точки
            cursor.execute("""
                INSERT INTO promo_usage_by_point (point_name, promo_code, used_count, last_used_at)
                VALUES (%s, %s, 1, NOW())
                ON DUPLICATE KEY UPDATE 
                    used_count = used_count + 1,
                    last_used_at = NOW()
            """, (point_name, code))
            
            # 3. Получаем текущее состояние
            cursor.execute("""
                SELECT used_count, total_amount 
                FROM promo_codes 
                WHERE code = %s AND is_deleted = FALSE
            """, (code,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            used_count = row["used_count"]
            total_amount = row["total_amount"]
            is_exhausted = used_count >= total_amount
            
            # 4. Если исчерпан — помечаем как удалённый
            if is_exhausted:
                cursor.execute("""
                    UPDATE promo_codes 
                    SET is_deleted = TRUE, deleted_at = NOW() 
                    WHERE code = %s
                """, (code,))
            
            conn.commit()
            
            return {
                "used_count": used_count,
                "total_amount": total_amount,
                "is_exhausted": is_exhausted
            }
    except Exception as e:
        print(f"[PromoDB] ❌ Ошибка записи использования: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_promo_status(code: str) -> Optional[Dict]:
    """Возвращает статус промокода из БД"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT code, total_amount, used_count, is_deleted, created_at, deleted_at
                FROM promo_codes WHERE code = %s
            """, (code,))
            return cursor.fetchone()
    except Exception as e:
        print(f"[PromoDB] ❌ Ошибка получения статуса: {e}")
        return None
    finally:
        conn.close()


def get_point_usage(code: str) -> List[Dict]:
    """Возвращает статистику использования промокода по точкам"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT point_name, used_count, last_used_at
                FROM promo_usage_by_point
                WHERE promo_code = %s
                ORDER BY used_count DESC
            """, (code,))
            return cursor.fetchall()
    except Exception as e:
        print(f"[PromoDB] ❌ Ошибка получения статистики: {e}")
        return []
    finally:
        conn.close()