"""
SmartShell API Module - Работа с GraphQL API SmartShell (синхронная версия для GUI)
"""
import requests
import os
from typing import List, Dict, Optional, Tuple
from config import (
    SMARTSHELL_GRAPHQL_URL, SMARTSHELL_V2_GRAPHQL_URL, SMARTSHELL_LOGIN, SMARTSHELL_PASSWORD,
    SMARTSHELL_WAREHOUSE_IDS
)


def get_access_token_sync(warehouse_name: str) -> Tuple[bool, str]:
    """
    Получает access_token из SmartShell для конкретной точки (синхронная версия)
    Returns: (success: bool, token_or_error: str)
    """
    if warehouse_name not in SMARTSHELL_WAREHOUSE_IDS:
        return False, f"Точка '{warehouse_name}' не найдена в конфигурации"
    
    company_id = SMARTSHELL_WAREHOUSE_IDS[warehouse_name]
    
    login_query = """
    mutation login {
        login(input: {
            login: "%s"
            password: "%s"
            company_id: %d
        }) {
            access_token
        }
    }
    """ % (SMARTSHELL_LOGIN, SMARTSHELL_PASSWORD, company_id)
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    try:
        response = requests.post(
            SMARTSHELL_GRAPHQL_URL.strip(),
            json={"query": login_query},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                return False, f"Login failed: {error_msg}"
            return True, data["data"]["login"]["access_token"]
        else:
            return False, f"HTTP {response.status_code}"
    
    except Exception as e:
        return False, f"Ошибка подключения: {str(e)}"


def create_good_in_smartshell(
    warehouse_name: str,
    title: str,
    cost: float,
    wholesale_cost: float,
    use_global_discounts: bool = False,
    subtitle: Optional[str] = None,
    comment: Optional[str] = None,
    tax_percent: Optional[float] = None,
    unit_name: Optional[str] = None,
    unit_value: Optional[float] = None,
    amount: Optional[int] = None,
    image: Optional[str] = None,
    vat: Optional[str] = None,
    eans: Optional[List[str]] = None,
    use_fair_sign: Optional[bool] = None,
    is_excise: Optional[bool] = None,
    price: Optional[float] = None,
    show_in_shell: Optional[bool] = None,
    low_stock_enabled: Optional[bool] = None,
    low_stock_threshold: Optional[int] = None,
    category_id: Optional[int] = None,
    highlighted: Optional[bool] = None
) -> Tuple[bool, str, Optional[int]]:
    """
    Создаёт товар в SmartShell для конкретной точки (через старый эндпоинт)
    
    Returns: (success: bool, message: str, good_id: Optional[int])
    """
    # Получаем токен
    success, token_or_error = get_access_token_sync(warehouse_name)
    if not success:
        return False, f"Ошибка авторизации: {token_or_error}", None
    
    access_token = token_or_error
    company_id = SMARTSHELL_WAREHOUSE_IDS[warehouse_name]
    
    # Формируем input для мутации
    input_data = {
        "title": title,
        "cost": cost,
        "wholesale_cost": wholesale_cost,
        "use_global_discounts": use_global_discounts
    }
    
    # Добавляем опциональные параметры
    if subtitle is not None:
        input_data["subtitle"] = subtitle
    if comment is not None:
        input_data["comment"] = comment
    if tax_percent is not None:
        input_data["tax_percent"] = tax_percent
    if unit_name is not None:
        input_data["unit_name"] = unit_name
    if unit_value is not None:
        input_data["unit_value"] = unit_value
    if amount is not None:
        input_data["amount"] = amount
    if image is not None:
        input_data["image"] = image
    if vat is not None:
        input_data["vat"] = vat
    if eans is not None:
        input_data["eans"] = eans
    if use_fair_sign is not None:
        input_data["use_fair_sign"] = use_fair_sign
    if is_excise is not None:
        input_data["is_excise"] = is_excise
    if price is not None:
        input_data["price"] = price
    if show_in_shell is not None:
        input_data["show_in_shell"] = show_in_shell
    if low_stock_enabled is not None or low_stock_threshold is not None:
        input_data["low_stock_notification"] = {
            "enabled": low_stock_enabled if low_stock_enabled is not None else False,
            "threshold": low_stock_threshold if low_stock_threshold is not None else 5
        }
    if category_id is not None:
        input_data["category_id"] = category_id
    if highlighted is not None:
        input_data["highlighted"] = highlighted
    
    # GraphQL мутация
    mutation = """
    mutation createGood($input: GoodInput!) {
        createGood(input: $input) {
            id
            title
            amount
            show_in_shell
            eans
            vat
            category {
                id
                company_id
                title
                show_in_shell
                __typename
            }
            low_stock_notification {
                enabled
                threshold
                __typename
            }
            __typename
        }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    try:
        response = requests.post(
            SMARTSHELL_GRAPHQL_URL.strip(),
            json={"query": mutation, "variables": {"input": input_data}},
            headers=headers,
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                return False, f"Ошибка API: {error_msg}", None
            
            good_data = data["data"]["createGood"]
            good_id = good_data["id"]
            return True, f"Товар создан (ID: {good_id})", good_id
        else:
            error_text = response.text[:200]
            return False, f"HTTP {response.status_code}: {error_text}", None
    
    except Exception as e:
        return False, f"Исключение: {str(e)}", None


def create_good_multiple_warehouses(
    warehouse_names: List[str],
    title: str,
    cost: float,
    wholesale_cost: float,
    use_global_discounts: bool = False,
    **kwargs
) -> Dict:
    """
    Создаёт товар в SmartShell на нескольких точках сразу
    
    Returns: {
        "success": [(warehouse, good_id), ...],
        "errors": [(warehouse, error_message), ...]
    }
    """
    result = {"success": [], "errors": []}
    
    for wh_name in warehouse_names:
        success, message, good_id = create_good_in_smartshell(
            warehouse_name=wh_name,
            title=title,
            cost=cost,
            wholesale_cost=wholesale_cost,
            use_global_discounts=use_global_discounts,
            **kwargs
        )
        
        if success:
            result["success"].append((wh_name, good_id))
        else:
            result["errors"].append((wh_name, message))
    
    return result


# ============================================================================
# === ПРОМОКОДЫ (V2 ЭНДПОИНТ) ===
# ============================================================================

def create_promo_campaign_in_smartshell(
    warehouse_name: str,
    title: str,
    value_type: str,
    value_amount: float,
    amount: int = 500,
    prefix: str = "PROMO",
    length: int = 6,
    code_type: str = "MIXED"
) -> Tuple[bool, str, Optional[int]]:
    """
    Создаёт кампанию промокодов в SmartShell через v2 эндпоинт (мутация createPromoCampaign).
    Позволяет задать тип (BONUS/DISCOUNT/DEPOSIT) и scopes (BILLING, MOBILE_APP, SHELL).
    
    Args:
        warehouse_name: Название точки (склада)
        title: Название кампании
        value_type: Тип вознаграждения (BONUS, DISCOUNT, DEPOSIT)
        value_amount: Значение вознаграждения
        amount: Количество генерируемых промокодов
        prefix: Префикс перед кодом
        length: Длина кода (6, 7 или 8)
        code_type: Формат кода (MIXED, SYMBOLS, NUMERIC)
        
    Returns: (success: bool, message: str, campaign_id: Optional[int])
    """
    success, token_or_error = get_access_token_sync(warehouse_name)
    if not success:
        return False, f"Ошибка авторизации: {token_or_error}", None
    
    access_token = token_or_error
    company_id = SMARTSHELL_WAREHOUSE_IDS[warehouse_name]
    
    # Формируем input ТОЧНО по спецификации разработчика
    input_data = {
        "title": title,
        "value": {
            "type": value_type,       # BONUS, DISCOUNT или DEPOSIT
            "value": float(value_amount)
        },
        "active": True,
        "is_tracked": False,          # Отключаем ТГ-уведомления
        "generation_settings": {
            "amount": amount,
            "length": length,
            "prefix": prefix,
            "type": code_type         # MIXED, SYMBOLS, NUMERIC
        },
        "applicable_params": {
            "goods": [-1],
            "services": [-1],
            "tariffs": [-1]
        },
        "scopes": ["BILLING", "MOBILE_APP", "SHELL"],
        "client_scope": {
            "groups": [],
            "users": []
        },
        "active_from": None,
        "active_to": None
    }
    
    # Мутация createPromoCampaign (как просил разработчик)
    query = """
    mutation CreatePromoCampaignV2($input: PromoCampaignInput!) {
      createPromoCampaign(input: $input) {
        id
        title
        description
        value {
          type
          value
        }
        applicable_params
        client_scope {
          ... on ScopedClient {
            avatar_url
            id
            phone
          }
          ... on ScopedGroup {
            id
            title
          }
        }
        scopes
        generation_settings {
          length
          prefix
          type
        }
        counters {
          total
          used
        }
        active
        active_from
        active_to
        is_tracked
        created_at
        updated_at
      }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    try:
        # ВАЖНО: используем V2 эндпоинт для промокодов!
        response = requests.post(
            SMARTSHELL_V2_GRAPHQL_URL,
            json={
                "query": query,
                "variables": {"input": input_data},
                "operationName": "CreatePromoCampaignV2"
            },
            headers=headers,
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                return False, f"Ошибка API: {error_msg}", None
            
            campaign_data = data["data"]["createPromoCampaign"]
            campaign_id = campaign_data["id"]
            campaign_title = campaign_data["title"]
            return True, f"Кампания '{campaign_title}' создана (ID: {campaign_id})", campaign_id
        else:
            error_text = response.text[:500]
            return False, f"HTTP {response.status_code}: {error_text}", None
    
    except Exception as e:
        return False, f"Исключение: {str(e)}", None


def create_promo_campaign_multiple_warehouses(
    warehouse_names: List[str],
    title: str,
    value_type: str,
    value_amount: float,
    amount: int = 500,
    prefix: str = "PROMO",
    length: int = 6,
    code_type: str = "MIXED"
) -> Dict:
    """
    Создаёт кампанию промокодов на нескольких точках сразу (через v2 эндпоинт).
    
    Returns: {
        "success": [(warehouse, campaign_id), ...],
        "errors": [(warehouse, error_message), ...]
    }
    """
    result = {"success": [], "errors": []}
    
    for wh_name in warehouse_names:
        success, message, campaign_id = create_promo_campaign_in_smartshell(
            warehouse_name=wh_name,
            title=title,
            value_type=value_type,
            value_amount=value_amount,
            amount=amount,
            prefix=prefix,
            length=length,
            code_type=code_type
        )
        
        if success:
            result["success"].append((wh_name, campaign_id))
        else:
            result["errors"].append((wh_name, message))
    
    return result


def debug_v2_promo_types(warehouse_name: str):
    """Интроспекция типов PromoCodeInput и PromoCodeEntityInput на V2 эндпоинте"""
    import json
    
    success, token_or_error = get_access_token_sync(warehouse_name)
    if not success:
        print(f"❌ Ошибка авторизации: {token_or_error}")
        return
    
    access_token = token_or_error
    company_id = SMARTSHELL_WAREHOUSE_IDS[warehouse_name]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    # Запрашиваем оба возможных типа на V2 эндпоинте
    query = """
    {
      promo_code_input: __type(name: "PromoCodeInput") {
        name
        inputFields { 
          name 
          type { 
            name 
            kind 
            ofType { name kind ofType { name kind } }
          } 
        }
      }
      promo_code_entity_input: __type(name: "PromoCodeEntityInput") {
        name
        inputFields { 
          name 
          type { 
            name 
            kind 
            ofType { name kind ofType { name kind } }
          } 
        }
      }
    }
    """
    
    try:
        # ВАЖНО: используем V2 эндпоинт!
        response = requests.post(
            SMARTSHELL_V2_GRAPHQL_URL,
            json={"query": query},
            headers=headers,
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "promo_v2_debug.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n✅ V2 интроспекция сохранена в файл: {output_path}\n")
            return data
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:300]}")
    except Exception as e:
        print(f"❌ Исключение: {e}")


def create_promocode_in_smartshell_v2(
    warehouse_name: str,
    code: str,
    value_type: str,
    value_amount: float,
    amount: int = 1
) -> Tuple[bool, str, Optional[int]]:
    """
    Создаёт ОДИНОЧНЫЙ промокод в SmartShell через v2 эндпоинт.
    Использует тип PromoCodeEntityInput (позволяет задать scopes, type BONUS и т.д.).
    """
    success, token_or_error = get_access_token_sync(warehouse_name)
    if not success:
        return False, f"Ошибка авторизации: {token_or_error}", None
    
    access_token = token_or_error
    company_id = SMARTSHELL_WAREHOUSE_IDS[warehouse_name]
    
    # Формируем input для PromoCodeEntityInput
    input_data = {
        "code": code,
        "value": {
            "type": value_type,       # BONUS, DISCOUNT или DEPOSIT
            "value": float(value_amount)
        },
        "amount": amount,
        "active": True,
        "is_tracked": False,          # Отключаем ТГ-уведомления
        "scopes": ["BILLING", "MOBILE_APP", "SHELL"]
    }
    
    # Мутация createPromoCode с типом PromoCodeEntityInput!
    query = """
    mutation CreatePromoCodeV2($input: PromoCodeEntityInput!) {
      createPromoCode(input: $input) {
        id
        code
        active
        is_tracked
        scopes
        value {
          type
          value
        }
        __typename
      }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    try:
        # ВАЖНО: используем V2 эндпоинт!
        response = requests.post(
            SMARTSHELL_V2_GRAPHQL_URL,
            json={
                "query": query,
                "variables": {"input": input_data},
                "operationName": "CreatePromoCodeV2"
            },
            headers=headers,
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                return False, f"Ошибка API: {error_msg}", None
            
            promo_data = data["data"]["createPromoCode"]
            promo_id = promo_data["id"]
            promo_code = promo_data["code"]
            return True, f"Промокод '{promo_code}' создан (ID: {promo_id})", promo_id
        else:
            error_text = response.text[:500]
            return False, f"HTTP {response.status_code}: {error_text}", None
    
    except Exception as e:
        return False, f"Исключение: {str(e)}", None


def create_promocode_multiple_warehouses_v2(
    warehouse_names: List[str],
    code: str,
    value_type: str,
    value_amount: float,
    amount: int = 1
) -> Dict:
    """Создаёт одиночный промокод на нескольких точках сразу (через v2)."""
    result = {"success": [], "errors": []}
    
    for wh_name in warehouse_names:
        success, message, promo_id = create_promocode_in_smartshell_v2(
            warehouse_name=wh_name,
            code=code,
            value_type=value_type,
            value_amount=value_amount,
            amount=amount
        )
        
        if success:
            result["success"].append((wh_name, promo_id))
        else:
            result["errors"].append((wh_name, message))
    
    # === ВАЖНО: Регистрируем промокод в БД ===
    if result["success"]:
        print(f"[SmartShell API] 📝 Регистрируем промокод '{code}' в БД...")
        try:
            from promo_db import register_promo_code
            register_promo_code(code=code, total_amount=amount)
        except Exception as e:
            print(f"[SmartShell API] ❌ Ошибка при регистрации в БД: {e}")
            import traceback
            traceback.print_exc()
    
    return result

from config import (
    SMARTSHELL2_GRAPHQL_URL, SMARTSHELL2_V2_GRAPHQL_URL,
    SMARTSHELL2_LOGIN, SMARTSHELL2_PASSWORD
)


def get_access_token_monitor(company_id: int) -> Tuple[bool, str]:
    """Авторизация второго аккаунта через СТАРЫЙ эндпоинт (EventList там)."""
    login_query = """
    mutation login {
        login(input: {
            login: "%s"
            password: "%s"
            company_id: %d
        }) {
            access_token
        }
    }
    """ % (SMARTSHELL2_LOGIN, SMARTSHELL2_PASSWORD, company_id)
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    try:
        response = requests.post(
            SMARTSHELL2_GRAPHQL_URL,
            json={"query": login_query},
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                return False, data["errors"][0].get("message", "Login error")
            return True, data["data"]["login"]["access_token"]
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def fetch_promo_used_events(access_token: str, company_id: int, start_time: str, finish_time: str) -> List[Dict]:
    """Получает события PROMO_CODE_USED через СТАРЫЙ эндпоинт (EventList)."""
    query = """
    query EventList($input: EventsInput, $page: Int, $first: Int) {
      eventList(input: $input, page: $page, first: $first) {
        data {
          timestamp
          type
          description
          client { uuid phone first_name last_name __typename }
          promo_code_item { id title value __typename }
        }
        paginatorInfo { currentPage lastPage total __typename }
      }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    variables = {
        "input": {
            "start": start_time,
            "finish": finish_time,
            "types": ["PROMO_CODE_USED"]
        },
        "page": 1,
        "first": 100
    }
    
    # ОТЛАДКА: выводим полный запрос
    print(f"[PromoMonitor DEBUG] EventList запрос: start={start_time}, finish={finish_time}, company_id={company_id}")
    
    try:
        response = requests.post(
            SMARTSHELL2_GRAPHQL_URL,
            json={"query": query, "variables": variables, "operationName": "EventList"},
            headers=headers,
            timeout=15
        )
        
        # ОТЛАДКА: выводим полный ответ
        print(f"[PromoMonitor DEBUG] EventList HTTP {response.status_code}")
        print(f"[PromoMonitor DEBUG] EventList ответ: {response.text[:1000]}")
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                print(f"[PromoMonitor DEBUG] EventList ошибки: {data['errors']}")
            return data.get("data", {}).get("eventList", {}).get("data", [])
        else:
            print(f"[PromoMonitor DEBUG] EventList ошибка HTTP: {response.text[:500]}")
    except Exception as e:
        print(f"[PromoMonitor DEBUG] EventList исключение: {e}")
    return []

def find_promo_by_code_v2(access_token: str, company_id: int, code: str) -> Optional[Dict]:
    """
    Ищет промокод по его code через V2 эндпоинт (PromoCodesListV2).
    Получает список промокодов и ищет нужный в памяти.
    """
    query = """
    query PromoCodesListV2($page: Int, $count: Int) {
      promoCodesList(page: $page, count: $count) {
        items {
          id
          code
          amount
          active
          active_from
          active_to
          is_tracked
          scopes
          value { type value __typename }
          counters { used __typename }
          created_at
          __typename
        }
        paginatorInfo { count currentPage lastPage total __typename }
      }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    try:
        response = requests.post(
            SMARTSHELL2_V2_GRAPHQL_URL,
            json={
                "query": query,
                "variables": {"page": 1, "count": 100},
                "operationName": "PromoCodesListV2"
            },
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("promoCodesList", {}).get("items", [])
            
            # Ищем нужный промокод (без учёта регистра)
            code_lower = code.lower()
            for item in items:
                if item.get("code", "").lower() == code_lower:
                    return item
            
            # Если не нашли — проверяем остальные страницы
            paginator = data.get("data", {}).get("promoCodesList", {}).get("paginatorInfo", {})
            last_page = paginator.get("lastPage", 1)
            
            if last_page > 1:
                for page in range(2, min(last_page + 1, 10)):
                    response = requests.post(
                        SMARTSHELL2_V2_GRAPHQL_URL,
                        json={
                            "query": query,
                            "variables": {"page": page, "count": 100},
                            "operationName": "PromoCodesListV2"
                        },
                        headers=headers,
                        timeout=15
                    )
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("data", {}).get("promoCodesList", {}).get("items", [])
                        for item in items:
                            if item.get("code", "").lower() == code_lower:
                                return item
        else:
            print(f"[PromoMonitor] PromoCodesListV2 HTTP {response.status_code}: {response.text[:500]}")
    except Exception as e:
        print(f"[PromoMonitor] Ошибка PromoCodesListV2: {e}")
    return None

def update_promo_amount_v2(
    access_token: str,
    company_id: int,
    promo_id: int,
    new_amount: int,
    current_promo: Dict
) -> Tuple[bool, str, Optional[Dict]]:
    """Обновляет amount промокода через V2 эндпоинт (UpdatePromoCodeV2)."""
    query = """
    mutation UpdatePromoCodeV2($id: Int!, $input: UpdatePromoCodeEntityInput!) {
      updatePromoCode(id: $id, input: $input) {
        id
        code
        amount
        active
        value { type value __typename }
        scopes
        is_tracked
        __typename
      }
    }
    """
    
    value_data = current_promo.get("value", {})
    
    input_data = {
        "code": current_promo.get("code"),
        "value": {
            "type": value_data.get("type"),
            "value": float(value_data.get("value", 0))
        },
        "active": current_promo.get("active", True),
        "is_tracked": current_promo.get("is_tracked", False),
        "scopes": current_promo.get("scopes") or ["BILLING", "MOBILE_APP", "SHELL"],
        "amount": new_amount,
        "applicable_params": current_promo.get("applicable_params"),
        "client_scope": current_promo.get("client_scope"),
        "active_from": current_promo.get("active_from"),
        "active_to": current_promo.get("active_to")
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    try:
        response = requests.post(
            SMARTSHELL2_V2_GRAPHQL_URL,
            json={
                "query": query,
                "variables": {"id": promo_id, "input": input_data},
                "operationName": "UpdatePromoCodeV2"
            },
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                return False, data["errors"][0].get("message", "Update error"), None
            updated = data["data"]["updatePromoCode"]
            
            # ОТЛАДКА: выводим, что именно вернул сервер
            print(f"[PromoMonitor DEBUG] UpdatePromoCode ответ: id={updated.get('id')}, amount={updated.get('amount')}, code={updated.get('code')}")
            print(f"[PromoMonitor DEBUG] Ожидали: id={promo_id}, amount={new_amount}")
            
        
        return False, f"HTTP {response.status_code}", None
    except Exception as e:
        return False, str(e), None

def delete_promo_v2(
    access_token: str,
    company_id: int,
    promo_id: int
) -> Tuple[bool, str, Optional[Dict]]:
    """
    Удаляет промокод через V2 эндпоинт (DeletePromoCodeV2).
    Используется, когда amount = 1 и промокод исчерпан.
    """
    query = """
    mutation DeletePromoCodeV2($id: Int!) {
      deletePromoCode(id: $id) {
        id
        code
        __typename
      }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": f"company_id={company_id}"
    }
    
    try:
        response = requests.post(
            SMARTSHELL2_V2_GRAPHQL_URL,
            json={
                "query": query,
                "variables": {"id": promo_id},
                "operationName": "DeletePromoCodeV2"
            },
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                return False, data["errors"][0].get("message", "Delete error"), None
            deleted = data["data"]["deletePromoCode"]
            if deleted["id"] == promo_id:
                return True, f"OK: промокод удалён (code={deleted.get('code')})", deleted
            return False, f"Верификация провалена (вернулся id={deleted.get('id')})", deleted
        
        return False, f"HTTP {response.status_code}: {response.text[:200]}", None
    except Exception as e:
        return False, str(e), None