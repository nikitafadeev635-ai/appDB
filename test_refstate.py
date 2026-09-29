"""Тест модуля refstate_repository"""
from refstate_repository import RefStateRepository

repo = RefStateRepository()

print("=" * 60)
print("🔌 Подключение к БД...")
print("=" * 60)
if not repo.connect():
    print("❌ Не удалось подключиться!")
    exit(1)
print("✅ Подключено!")

print("\n" + "=" * 60)
print("📊 Общая статистика")
print("=" * 60)
stats = repo.get_total_stats()
print(f"  Всего записей: {stats['total_records']}")
print(f"  Администраторов: {stats['total_admins']}")
print(f"  Общая сумма: {stats['total_value']:.2f}₽")

print("\n" + "=" * 60)
print("👤 Список администраторов")
print("=" * 60)
admins = repo.get_administrators_summary()
for admin in admins:
    print(f"  • {admin['administrator']}")
    print(f"    Записей: {admin['records_count']}")
    print(f"    Сумма: {admin['total_value']:.2f}₽")
    print(f"    Последняя: {admin['last_created']}")

print("\n" + "=" * 60)
print("📋 Записи первого администратора")
print("=" * 60)
if admins:
    first_admin = admins[0]["administrator"]
    records = repo.get_records_by_admin(first_admin)
    for rec in records:
        print(f"  [{rec['id']}] {rec['product_title']}")
        print(f"      Кол-во: {rec['quantity']} шт")
        print(f"      Сумма: {rec['value']:.2f}₽")
        print(f"      Причина: {rec['reason']}")
        print(f"      Ссылка: {rec['reference']}")
        print()

print("\n" + "=" * 60)
print("💾 Тест бэкапа")
print("=" * 60)
backup_result = repo.backup_table()
print(f"  Успех: {backup_result['success']}")
print(f"  Файл: {backup_result['file_path']}")
print(f"  Записей: {backup_result['records_count']}")
print(f"  Сообщение: {backup_result['message']}")

repo.disconnect()
print("\n✅ Тест завершён!")