from typing import Any, Dict, List, Optional


def of(
        items: List[Any],
        pagination_key: Optional[str]) -> Dict[str, Any]:

    return {
        "items": items,
        "paginationKey": pagination_key,
    }


def get_items(list_result: Dict[str, Any]) -> List[Any]:
    return list_result["items"]


def get_pagination_key(list_result: Dict[str, Any]) -> Optional[str]:
    return list_result.get("paginationKey")
