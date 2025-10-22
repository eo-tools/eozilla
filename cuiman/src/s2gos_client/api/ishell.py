#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import importlib.util
from typing import Any, Callable

has_ishell = importlib.util.find_spec("IPython.core.interactiveshell")
exception_handler: Callable[[Any, Any, Any, Any], None] | None = None

__all__ = ["has_ishell", "exception_handler"]


def _register_exception_handler() -> Callable[[Any, Any, Any, Any], None]:
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.display import JSON, display

    from .exceptions import ClientError

    # noinspection PyUnusedLocal
    def handle_exception(
        self: InteractiveShell, exc_type, exc_value, tb, tb_offset=None
    ):
        if isinstance(exc_value, ClientError):
            display(
                JSON(
                    exc_value.api_error.model_dump(mode="json", exclude_none=True),
                    root="Client error",
                    expanded=True,
                )
            )
            return None, None, None  # prevents default traceback

        return None

    # Register handler for MyCustomError
    InteractiveShell.instance().set_custom_exc((ClientError,), handle_exception)
    return handle_exception


if has_ishell:
    exception_handler = _register_exception_handler()
