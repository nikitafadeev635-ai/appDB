"""
SmartShell API Module - Функции для PromoMonitor Daemon
- get_access_token_monitor — авторизация второго аккаунта для конкретной точки
- fetch_promo_used_events — чтение событий PROMO_CODE_USED (СТАРЫЙ эндпоинт)
- find_promo_by_code_v2 — поиск промокода по коду (V2 эндпоинт)
- delete_promo_v2 — удаление промокода (V2 эндпоинт)
"""
import requests
from typing import List, Dict, Optional, Tuple
from config import (
    SMARTSHELL2_GRAPHQL_URL, SMARTSHELL2_V2_GRAPHQL_URL,
    SMARTSHELL2_LOGIN, SMARTSHELL2_PASSWORD
)


def get_access_token_monitor(company_id: int) -> Tuple[bool, str]:
    """Авторизация второго аккаунта через СТАРЫЙ эндпоинт для конкретной точки."""
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
    
    try:
        response = requests.post(
            SMARTSHELL2_GRAPHQL_URL,
            json={"query": query, "variables": variables, "operationName": "EventList"},
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                print(f"[PromoMonitor] ⚠️ EventList ошибки: {data['errors']}")
            return data.get("data", {}).get("eventList", {}).get("data", [])
        else:
            print(f"[PromoMonitor] ⚠️ EventList HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[PromoMonitor] ❌ EventList исключение: {e}")
    return []


def find_promo_by_code_v2(access_token: str, company_id: int, code: str) -> Optional[Dict]:
    """Ищет промокод по коду через V2 эндпоинт (PromoCodesListV2)."""
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
        # Получаем первую страницу
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
            print(f"[PromoMonitor] PromoCodesListV2 HTTP {response.status_code}: {response.text[:300]}")
    except Exception as e:
        print(f"[PromoMonitor] Ошибка PromoCodesListV2: {e}")
    return None


def delete_promo_v2(
    access_token: str,
    company_id: int,
    promo_id: int
) -> Tuple[bool, str, Optional[Dict]]:
    """Удаляет промокод через V2 эндпоинт (DeletePromoCodeV2)."""
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
            return False, f"Верификация провалена (id={deleted.get('id')})", deleted
        
        return False, f"HTTP {response.status_code}: {response.text[:200]}", None
    except Exception as e:
        return False, str(e), None