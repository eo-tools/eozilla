#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable


def ensure_type(name: str, value: Any, expected_type: type | tuple[type, ...]) -> None:
    """Raise a `TypeError` if `value` is not of type `expected_type`."""
    if not isinstance(value, expected_type):
        if isinstance(expected_type, tuple):
            type_text = " or ".join(t.__name__ for t in expected_type)
        else:
            type_text = expected_type.__name__
        actual_type = type(value)
        raise TypeError(
            f"{name} must have type {type_text}, but was {actual_type.__name__}"
        )


def ensure_callable(name: str, value: Any) -> None:
    """Raise a `TypeError` if `value` is not callable."""
    if not callable(value):
        actual_type = type(value)
        raise TypeError(f"{name} must be callable, but was {actual_type.__name__}")


def ensure_condition(
    condition: bool,
    message: str | Callable[[], str],
    exception_type: type[Exception] = ValueError,
) -> None:
    """Raise a `ValueError` if `condition` is `False`."""
    if not condition:
        raise exception_type(message() if callable(message) else message)
