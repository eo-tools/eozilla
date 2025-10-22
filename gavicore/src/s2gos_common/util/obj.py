#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any


def flatten_obj(
    obj: Any, *, parent_key: str = "", sep: str = ".", flatten_lists: bool = False
) -> dict[str, Any]:
    return _flatten_obj(
        obj, parent_key=parent_key, sep=sep, flatten_lists=flatten_lists
    )


def _flatten_obj(
    obj: Any,
    parent_key: str = "",
    sep: str = ".",
    flatten_lists: bool = False,
) -> dict[str, Any]:
    """
    Flatten nested dicts/lists into a flat dict with sep-delimited keys.

    Args:
        obj: The nested structure (dict, list, or scalar).
        parent_key: Internal recursion prefix for keys.
        sep: Separator string for flattened keys.
        flatten_lists: If True, expand lists into indexed keys (default).
                       If False, keep lists as values (without flattening inside).

    Returns:
        A flat dictionary mapping sep-delimited keys to values.
    """
    items: dict[str, Any] = {}

    if isinstance(obj, dict) and len(obj) > 0:
        for k, v in obj.items():
            _update_flattened_items(k, v, parent_key, flatten_lists, sep, items)
    elif isinstance(obj, list) and len(obj) > 0 and flatten_lists:
        for i, v in enumerate(obj):
            if v is None:  # skip None placeholders
                continue
            _update_flattened_items(i, v, parent_key, flatten_lists, sep, items)
    elif parent_key:
        items[parent_key] = obj

    return items


def _update_flattened_items(
    k,
    v,
    parent_key: str,
    flatten_lists: bool,
    sep: str,
    items: dict[str, Any],
):
    new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
    flattened_v = _flatten_obj(
        v, parent_key=new_key, flatten_lists=flatten_lists, sep=sep
    )
    items.update(flattened_v)


def nest_dict(flatted_dict: dict[str, Any], *, sep: str = ".") -> dict[str, Any]:
    """Nest a flat dict with sep-delimited keys back into a dicts."""
    root = nest_obj(flatted_dict, sep=sep, root={})
    assert isinstance(root, dict)
    return root


def nest_obj(
    flatted_dict: dict[str, Any],
    *,
    sep: str = ".",
    root: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any] | list[Any] | None:
    """Nest a flat dict with sep-delimited keys back into dicts/lists."""
    # TODO: respect flatten_lists
    for k, v in flatted_dict.items():
        root = _nest_one(root, k, v, sep=sep)
    return root


def _nest_one(
    root: dict[str, Any] | list[Any] | None,
    name: str,
    value: Any,
    sep: str = ".",
) -> dict[str, Any] | list[Any] | None:
    keys = _parse_path(name, sep)

    current: Any = None
    prev: Any | None = None

    for i, key_or_index in enumerate(keys):
        if root is None:
            root = [] if isinstance(key_or_index, int) else {}
        if i == 0:
            current = root
        if current is None and prev is not None:
            current = prev[keys[i - 1]] = [] if isinstance(key_or_index, int) else {}
        prev = current
        current = _prepare_path(prev, key_or_index)

    assert prev is not None
    prev[keys[-1]] = value
    return root


def _prepare_path(current: dict[str, Any] | list[Any], key_or_index: str | int) -> Any:
    if isinstance(current, list):
        if not isinstance(key_or_index, int):
            raise TypeError(
                f"expected index of type int, got {type(key_or_index).__name__}"
            )
        index: int = key_or_index
        current_list: list[Any] = current
        while len(current_list) <= index:
            current_list.append(None)  # This is a Fill-value
        return current_list[index]
    elif isinstance(current, dict):
        if isinstance(key_or_index, int):
            raise TypeError(
                f"expected key of type str, got {type(key_or_index).__name__}"
            )
        key: str = key_or_index
        current_dict: dict[str, Any] = current
        if key not in current_dict:
            current_dict[key] = None  # This is a Fill-value
        return current_dict[key]
    raise TypeError(f"expected a list or a dict, got {type(current).__name__}")


def _parse_path(name: str, sep: str = ".") -> list[str | int]:
    keys: list[str] = name.split(sep)
    return [(int(key) if all(c.isdigit() for c in key) else key) for key in keys]
