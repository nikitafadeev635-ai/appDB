"""
PromoCode Monitor - Монитор событий PROMO_CODE_USED (серверная версия).
- Параллельный опрос всех точек
- finish_time = now() + 7ч (компенсация часового пояса Ульяновска UTC+10 vs сервер UTC+3)
- Состояние (last_event_timestamp) хранится в БД
"""
import threading
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple

from config import SMARTSHELL_WAREHOUSE_IDS
from smartshell_api import (
    get_access_token_monitor,
    fetch_promo_used_events,
    find_promo_by_code_v2,
    delete_promo_v2
)
from promo_db import (
    is_event_processed,
    mark_event_processed,
    record_promo_usage,
    load_last_timestamp,
    save_last_timestamp
)

# Сдвиг для компенсации часового пояса (Ульяновск UTC+10, сервер UTC+3 = разница 7ч)
TIMEZONE_OFFSET_HOURS = 7


class PromoCodeMonitor:
    """Фоновый монитор событий использования промокодов"""

    def __init__(self, poll_interval: int = 10):
        self.poll_interval = poll_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Токены для каждой точки: {company_id: {"token": str, "expiry": timestamp}}
        self.tokens: Dict[int, Dict] = {}
        self.tokens_lock = threading.Lock()
        
        # Загружаем timestamp из БД (переживает перезапуск)
        saved_ts = load_last_timestamp()
        if saved_ts:
            self.last_event_timestamp = saved_ts.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[PromoMonitor] 📂 Восстановлен timestamp из БД: {self.last_event_timestamp}")
        else:
            # Если БД пуста — начинаем с текущего момента минус 1 час (на всякий случай)
            self.last_event_timestamp = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[PromoMonitor] 🕒 Инициализация timestamp: {self.last_event_timestamp}")
        
        # In-memory кэш дедупликации
        self.processed_events: Set[tuple] = set()
        self.max_processed_cache = 2000

    def _ensure_all_tokens(self) -> bool:
        """Обновляет токены для ВСЕХ точек"""
        all_ok = True
        for wh_name, company_id in SMARTSHELL_WAREHOUSE_IDS.items():
            with self.tokens_lock:
                token_data = self.tokens.get(company_id)
                if token_data and time.time() < token_data["expiry"]:
                    continue
            
            success, token_or_err = get_access_token_monitor(company_id)
            if success:
                with self.tokens_lock:
                    self.tokens[company_id] = {
                        "token": token_or_err,
                        "expiry": time.time() + 3300
                    }
                print(f"[PromoMonitor] ✅ Токен обновлён для точки: {wh_name} (ID: {company_id})")
            else:
                print(f"[PromoMonitor] ❌ Ошибка авторизации для {wh_name} (ID: {company_id}): {token_or_err}")
                all_ok = False
        return all_ok

    def _get_token(self, company_id: int) -> Optional[str]:
        with self.tokens_lock:
            token_data = self.tokens.get(company_id)
            if token_data and time.time() < token_data["expiry"]:
                return token_data["token"]
        return None

    def _fetch_events_for_point(self, wh_name: str, company_id: int, start_time: str, finish_time: str) -> List[Tuple[Dict, str]]:
        """Опрашивает одну точку (выполняется параллельно в ThreadPoolExecutor)"""
        token = self._get_token(company_id)
        if not token:
            return []
        
        try:
            events = fetch_promo_used_events(token, company_id, start_time, finish_time)
            if events:
                return [(event, wh_name) for event in events]
        except Exception as e:
            print(f"[PromoMonitor] ⚠️ Ошибка опроса {wh_name}: {e}")
        return []

    def _process_event(self, event: Dict, source_point: str):
        """Обрабатывает одно событие PROMO_CODE_USED"""
        timestamp = event.get("timestamp")
        promo_item = event.get("promo_code_item")
        client = event.get("client") or {}
        
        if not promo_item:
            return
        
        code = promo_item.get("title")
        if not code:
            return
        
        client_uuid = client.get("uuid") or "unknown"
        client_name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
        client_phone = client.get("phone", "")
        
        # 1. Дедупликация через БД
        event_key = f"{timestamp}|{client_uuid}|{code}"
        if is_event_processed(event_key):
            return
        
        print(f"\n[PromoMonitor] 🎟️ Использован промокод: {code}")
        print(f"   👤 {client_name} ({client_phone})")
        print(f"   📍 Точка-инициатор: {source_point}")
        print(f"   🕒 {timestamp}")
        
        # 2. Записываем использование в БД
        usage_result = record_promo_usage(code=code, point_name=source_point)
        
        if not usage_result:
            print(f"   ⚠️ Промокод '{code}' не зарегистрирован в БД, пропускаем")
            return
        
        # 3. Помечаем событие как обработанное
        mark_event_processed(event_key)
        self.processed_events.add(event_key)
        if len(self.processed_events) > self.max_processed_cache:
            self.processed_events = set(list(self.processed_events)[-1000:])
        
        used_count = usage_result["used_count"]
        total_amount = usage_result["total_amount"]
        is_exhausted = usage_result["is_exhausted"]
        remaining = total_amount - used_count
        
        print(f"   📊 Статистика: {used_count}/{total_amount} использовано, осталось: {remaining}")
        
        if is_exhausted:
            # Промокод исчерпан — удаляем со всех точек
            print(f"   🗑️ Лимит исчерпан! Удаляем '{code}' со всех точек...")
            
            for wh_name, company_id in SMARTSHELL_WAREHOUSE_IDS.items():
                token = self._get_token(company_id)
                if not token:
                    print(f"   ⚠️ [{wh_name}] Нет рабочего токена")
                    continue
                
                promo_data = find_promo_by_code_v2(token, company_id, code)
                if not promo_data:
                    print(f"   ⏭️ [{wh_name}] Промокод уже не найден")
                    continue
                
                promo_id = promo_data.get("id")
                success, msg, deleted = delete_promo_v2(token, company_id, promo_id)
                
                if success:
                    print(f"   ✅ [{wh_name}] Удалён (ID={promo_id})")
                else:
                    print(f"   ❌ [{wh_name}] Ошибка удаления: {msg}")
        else:
            print(f"   ✅ Промокод '{code}' продолжает работать (осталось: {remaining})")

    def _monitor_loop(self):
        """Основной цикл мониторинга"""
        print(f"[PromoMonitor] 🚀 Запущен (интервал: {self.poll_interval}с)")
        print(f"[PromoMonitor] 📋 Точки: {list(SMARTSHELL_WAREHOUSE_IDS.keys())}")
        print(f"[PromoMonitor] 🕒 Старт с: {self.last_event_timestamp}")
        print(f"[PromoMonitor] 🌍 Сдвиг часового пояса: +{TIMEZONE_OFFSET_HOURS}ч")
        
        cycle_count = 0
        
        while self.running:
            try:
                cycle_count += 1
                
                if not self._ensure_all_tokens():
                    print("[PromoMonitor] ⏸️ Не все токены получены, ждём...")
                    time.sleep(self.poll_interval)
                    continue
                
                start_time = self.last_event_timestamp
                # КЛЮЧЕВОЕ: finish_time = now() + 7ч (компенсация ЧП)
                finish_time = (datetime.now() + timedelta(hours=TIMEZONE_OFFSET_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
                
                # Параллельный опрос всех точек
                all_events_with_source: List[Tuple[Dict, str]] = []
                
                with ThreadPoolExecutor(max_workers=len(SMARTSHELL_WAREHOUSE_IDS)) as executor:
                    futures = {
                        executor.submit(
                            self._fetch_events_for_point,
                            wh_name, company_id, start_time, finish_time
                        ): wh_name
                        for wh_name, company_id in SMARTSHELL_WAREHOUSE_IDS.items()
                    }
                    
                    for future in as_completed(futures):
                        wh_name = futures[future]
                        try:
                            events = future.result()
                            if events:
                                print(f"[PromoMonitor] 📨 [{wh_name}] Получено событий: {len(events)}")
                                all_events_with_source.extend(events)
                        except Exception as e:
                            print(f"[PromoMonitor] ⚠️ Ошибка при обработке {wh_name}: {e}")
                
                if all_events_with_source:
                    # Сортируем по timestamp
                    all_events_with_source.sort(key=lambda x: x[0].get("timestamp", ""))
                    
                    # Дедупликация по (timestamp, client_uuid, code)
                    unique_events: List[Tuple[Dict, str]] = []
                    seen = set()
                    for ev, source in all_events_with_source:
                        key = (
                            ev.get("timestamp"),
                            (ev.get("client") or {}).get("uuid", "x"),
                            (ev.get("promo_code_item") or {}).get("title", "x")
                        )
                        if key not in seen:
                            seen.add(key)
                            unique_events.append((ev, source))
                    
                    print(f"[PromoMonitor] 📊 Уникальных событий: {len(unique_events)}")
                    
                    for event, source_point in unique_events:
                        self._process_event(event, source_point=source_point)
                    
                    # Сдвигаем timestamp на +1 секунду и сохраняем в БД
                    last_ts = unique_events[-1][0].get("timestamp")
                    try:
                        dt = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
                        dt += timedelta(seconds=1)
                        self.last_event_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        self.last_event_timestamp = last_ts
                    
                    try:
                        dt_save = datetime.strptime(self.last_event_timestamp, "%Y-%m-%d %H:%M:%S")
                        save_last_timestamp(dt_save)
                    except Exception as e:
                        print(f"[PromoMonitor] ⚠️ Не удалось сохранить timestamp в БД: {e}")
                    
                    print(f"[PromoMonitor] 🕒 timestamp обновлён: {self.last_event_timestamp}")
                else:
                    if cycle_count % 6 == 0:
                        print(f"[PromoMonitor] 💤 Новых событий нет (цикл {cycle_count})")
                
                time.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"[PromoMonitor] ❌ Ошибка в цикле: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.poll_interval)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Останавливает монитор и сохраняет текущий timestamp"""
        print("[PromoMonitor] ⏹️ Останавливаю монитор...")
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        try:
            dt_save = datetime.strptime(self.last_event_timestamp, "%Y-%m-%d %H:%M:%S")
            save_last_timestamp(dt_save)
            print(f"[PromoMonitor] 💾 Финальный timestamp сохранён: {self.last_event_timestamp}")
        except Exception as e:
            print(f"[PromoMonitor] ⚠️ Не удалось сохранить финальный timestamp: {e}")
        print("[PromoMonitor] ⏹️ Остановлен")