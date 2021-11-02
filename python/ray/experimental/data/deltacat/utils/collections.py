from ray.experimental.data.deltacat.storage.model import list_result as lr
from typing import List, Any, Callable


def all_list_results(
        list_result_producer: Callable,
        *args,
        **kwargs) -> List[Any]:

    """
    Eagerly loads and returns a flattened list of all pages of items from the
    input list result producer.

    Args:
        list_result_producer (Callable): Function to invoke that returns a
        paginated list result.
        *args: Ordered input arguments to the list result producer.
        **kwargs: Keyword arguments to the list result producer. Any pagination
        key given will be ignored.
    Returns:
        items (List[Any]): Flattened list of items from all list result pages.
    """

    page_key = ""
    items = []
    while page_key is not None:
        kwargs["pagination_key"] = page_key
        list_result = list_result_producer(*args, **kwargs)
        items.extend(lr.get_items(list_result))
        page_key = lr.get_pagination_key(list_result)
    return items
