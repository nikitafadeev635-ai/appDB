# check_structure.py (создайте временно в корне проекта)
from config import DB_CONFIG
import pymysql

conn = pymysql.connect(
    host=DB_CONFIG["host"],
    user=DB_CONFIG["user"],
    password=DB_CONFIG["password"],
    database=DB_CONFIG["database"],
    port=int(DB_CONFIG["port"]),
    charset=DB_CONFIG.get("charset", "utf8mb4"),
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cursor:
    # 1. Структура таблицы refStateDetailed
    print("=" * 60)
    print("📋 Структура таблицы refStateDetailed:")
    print("=" * 60)
    cursor.execute("DESCRIBE refStateDetailed")
    for row in cursor.fetchall():
        print(f"  {row['Field']:<25} {row['Type']:<30} {row['Null']:<5} {row['Key']}")
    
    # 2. Пример данных (первые 3 строки)
    print("\n" + "=" * 60)
    print("📊 Пример данных (первые 3 строки):")
    print("=" * 60)
    cursor.execute("SELECT * FROM refStateDetailed LIMIT 3")
    for row in cursor.fetchall():
        print(row)
    
    # 3. Уникальные администраторы
    print("\n" + "=" * 60)
    print("👤 Уникальные администраторы:")
    print("=" * 60)
    cursor.execute("SELECT DISTINCT administrator FROM refStateDetailed ORDER BY administrator")
    for row in cursor.fetchall():
        print(f"  • {row['administrator']}")
    
    # 4. Количество строк
    cursor.execute("SELECT COUNT(*) as total FROM refStateDetailed")
    total = cursor.fetchone()["total"]
    print(f"\n📊 Всего записей: {total}")

conn.close()