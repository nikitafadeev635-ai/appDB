"""Диагностика таблицы processed_invoices"""
from config import DB_CONFIG
import pymysql

conn = pymysql.connect(
    host=DB_CONFIG["host"],
    user=DB_CONFIG["user"],
    password=DB_CONFIG["password"],
    database=DB_CONFIG["database"],
    port=int(DB_CONFIG["port"]),
    charset=DB_CONFIG.get("charset", "utf8mb4"),
    cursorclass=pymysql.cursors.DictCursor,
    connect_timeout=10,
    read_timeout=30,
)

with conn.cursor() as cursor:
    # 1. Общее количество записей
    print("=" * 60)
    print("📊 Проверка таблицы processed_invoices")
    print("=" * 60)
    
    cursor.execute("SELECT COUNT(*) as total FROM processed_invoices")
    total = cursor.fetchone()["total"]
    print(f"  Всего записей в таблице: {total}")
    
    # 2. Количество записей с разными значениями
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN invoice_number IS NULL THEN 1 ELSE 0 END) as null_numbers,
            SUM(CASE WHEN invoice_number = '' THEN 1 ELSE 0 END) as empty_numbers,
            SUM(CASE WHEN processed_at IS NULL THEN 1 ELSE 0 END) as null_dates,
            MIN(processed_at) as earliest,
            MAX(processed_at) as latest
        FROM processed_invoices
    """)
    stats = cursor.fetchone()
    print(f"\n  📈 Детальная статистика:")
    print(f"     Всего: {stats['total']}")
    print(f"     С пустым номером (NULL): {stats['null_numbers']}")
    print(f"     С пустым номером (''): {stats['empty_numbers']}")
    print(f"     Без даты: {stats['null_dates']}")
    print(f"     Самая ранняя: {stats['earliest']}")
    print(f"     Самая поздняя: {stats['latest']}")
    
    # 3. Проверка дубликатов по номеру
    cursor.execute("""
        SELECT invoice_number, COUNT(*) as cnt
        FROM processed_invoices
        GROUP BY invoice_number
        HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT 10
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"\n  🔄 Дубликаты номеров (топ-10):")
        for dup in duplicates:
            print(f"     '{dup['invoice_number']}' — {dup['cnt']} раз")
    else:
        print(f"\n  ✅ Дубликатов номеров не найдено")
    
    # 4. Тест полного чтения (как в программе)
    print("\n" + "=" * 60)
    print("🔍 Тест полного чтения (как в программе)")
    print("=" * 60)
    
    cursor.execute("""
        SELECT id, invoice_number, processed_at
        FROM processed_invoices
        ORDER BY processed_at DESC
    """)
    all_rows = cursor.fetchall()
    print(f"  Прочитано записей: {len(all_rows)}")
    
    # 5. Проверка с фильтрами (как может быть в программе)
    print("\n" + "=" * 60)
    print("🔍 Тест с различными условиями")
    print("=" * 60)
    
    # Без NULL номеров
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM processed_invoices
        WHERE invoice_number IS NOT NULL AND invoice_number != ''
    """)
    non_empty = cursor.fetchone()["cnt"]
    print(f"  Без пустых номеров: {non_empty}")
    
    # С датой за последний месяц
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM processed_invoices
        WHERE processed_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """)
    last_month = cursor.fetchone()["cnt"]
    print(f"  За последние 30 дней: {last_month}")
    
    # С датой за последнюю неделю
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM processed_invoices
        WHERE processed_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    """)
    last_week = cursor.fetchone()["cnt"]
    print(f"  За последние 7 дней: {last_week}")

conn.close()
print("\n✅ Диагностика завершена!")