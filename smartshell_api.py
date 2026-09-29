"""
SmartShell API Module - Работа с GraphQL API SmartShell (синхронная версия для GUI)
"""
import requests
from typing import List, Dict, Optional, Tuple
from config import (
    SMARTSHELL_GRAPHQL_URL, SMARTSHELL_LOGIN, SMARTSHELL_PASSWORD,
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
    Создаёт товар в SmartShell для конкретной точки
    
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