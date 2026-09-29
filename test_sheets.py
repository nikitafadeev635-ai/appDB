"""Тест подключения к Google Sheets"""
from google_sheets_client import GoogleSheetsClient

client = GoogleSheetsClient()

print("=" * 60)
print("🔌 Тест подключения к Google Sheets")
print("=" * 60)

result = client.test_connection()
print(f"  Успех: {result['success']}")
print(f"  Сообщение: {result['message']}")

if result['success']:
    print("\n" + "=" * 60)
    print("🔍 Поиск администратора")
    print("=" * 60)
    
    admin_name = "Александрова Александра"
    row = client.find_admin_row(admin_name)
    print(f"  Администратор: {admin_name}")
    print(f"  Строка: {row if row else '❌ НЕ НАЙДЕН'}")
    
    if row:
        print("\n✅ Всё готово для работы!")
    else:
        print("\n⚠️ Добавьте администратора в таблицу или проверьте написание")
else:
    print("\n❌ Проверьте credentials.json и GOOGLE_SHEETS_ID в .env")