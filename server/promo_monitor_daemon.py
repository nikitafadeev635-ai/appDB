"""
PromoMonitor Daemon - Точка входа для systemd.
"""
import signal
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from promo_db import init_promo_tables
from serverCore import PromoCodeMonitor

# Глобальный экземпляр (создаётся ПОСЛЕ инициализации БД)
monitor = None


def signal_handler(sig, frame):
    print(f"\n[PromoDaemon] 🛑 Получен сигнал {sig}, останавливаю монитор...")
    if monitor:
        monitor.stop()
    sys.exit(0)


def main():
    global monitor
    
    print("=" * 60)
    print("🚀 PromoMonitor Daemon - Запуск")
    print("=" * 60)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # === ШАГ 1: СНАЧАЛА инициализируем таблицы ===
    try:
        print("[PromoDaemon] 🔧 Инициализация таблиц БД...")
        init_promo_tables()
    except Exception as e:
        print(f"[PromoDaemon] ❌ Ошибка инициализации БД: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # === ШАГ 2: ТОЛЬКО ПОТОМ создаём монитор ===
    # Теперь load_last_timestamp() найдёт таблицу promo_monitor_state
    try:
        monitor = PromoCodeMonitor(poll_interval=10)
    except Exception as e:
        print(f"[PromoDaemon] ❌ Ошибка создания монитора: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # === ШАГ 3: Запускаем ===
    monitor.start()
    
    print("[PromoDaemon] ✅ Монитор запущен. Работаю круглосуточно...")
    print("[PromoDaemon] Нажмите Ctrl+C для остановки.")
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[PromoDaemon] 🛑 Остановка по Ctrl+C...")
        monitor.stop()


if __name__ == "__main__":
    main()