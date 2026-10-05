"""
Main Module - Точка входа в приложение
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_dependencies():
    missing = []
    try:
        import PySide6
    except ImportError:
        missing.append("PySide6")
    try:
        import pymysql
    except ImportError:
        missing.append("pymysql")
    try:
        import pandas
    except ImportError:
        missing.append("pandas")
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")

    if missing:
        print("❌ Отсутствуют необходимые библиотеки:")
        for lib in missing:
            print(f"   - {lib}")
        print("\nУстановите их командой:")
        print(f"   pip install {' '.join(missing)}")
        return False
    return True


def main():
    print("=" * 60)
    print("🚀 CyberMG - Система учёта склада")
    print("=" * 60)
    print()

    if not check_dependencies():
        input("\nНажмите Enter для выхода...")
        sys.exit(1)

    from config import DB_CONFIG

    if not DB_CONFIG.get("password") or DB_CONFIG["password"] in ["", "ВАШ_ПАРОЛЬ_ЗДЕСЬ"]:
        print("⚠️  Пароль базы данных не указан в core.py!")
        print("   Откройте файл core.py и заполните DB_CONFIG['password']\n")

        try:
            password = input("Введите пароль БД: ").strip()
            if password:
                DB_CONFIG["password"] = password
                print("✅ Пароль установлен\n")
            else:
                print("❌ Пароль не введён. Запуск невозможен.")
                input("\nНажмите Enter для выхода...")
                sys.exit(1)
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Ввод прерван. Укажите пароль в core.py и запустите снова.")
            input("\nНажмите Enter для выхода...")
            sys.exit(1)

    print("🔧 Инициализация интерфейса...")

    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtGui import QFont

    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    print("🔧 Подключение к базе данных и загрузка данных...")

    # Инициализация таблиц промокодов (до создания окна)
    from promo_db import init_promo_tables
    init_promo_tables()

    from gui import MainWindow

    try:
        window = MainWindow()
        window.show()
        print("✅ Приложение запущено!")

        # === ЗАПУСК МОНИТОРА ПРОМОКОДОВ ===
        #from server.serverCore import promo_monitor
        #promo_monitor.start()
        print("🚀 Монитор промокодов запущен в фоновом режиме")
        # ==================================

    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()

        QMessageBox.critical(
            None, "Критическая ошибка",
            f"Ошибка при запуске приложения:\n\n{str(e)}"
        )
        sys.exit(1)

    sys.exit(app.exec())
    
if __name__ == "__main__":
    main()