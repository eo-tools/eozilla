#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable


def ensure_type(
    name: str | Callable[[], str], value: Any, expected_type: type | tuple[type, ...]
) -> None:
    """Raise a `TypeError` if `value` is not of type `expected_type`."""
    if not isinstance(value, expected_type):
        if isinstance(expected_type, tuple):
            expected_msg = (
                f"one of the types {', '.join(t.__name__ for t in expected_type)}"
            )
        else:
            expected_msg = f"type {expected_type.__name__}"
        actual_type = type(value)
        raise TypeError(
            f"{name() if callable(name) else name} "
            f"must have {expected_msg} "
            f"but was {actual_type.__name__}"
        )


def ensure_callable(name: str | Callable[[], str], value: Any) -> None:
    """Raise a `TypeError` if `value` is not callable."""
    if not callable(value):
        actual_type = type(value)
        raise TypeError(
            f"{name() if callable(name) else name} must be callable "
            f"but was {actual_type.__name__}"
        )


def ensure_condition(condition: bool, message: str | Callable[[], str]) -> None:
    """Raise a `ValueError` if `condition` is `False`."""
    if not condition:
        raise ValueError(message() if callable(message) else message)
