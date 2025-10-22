#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import importlib
from typing import Optional, TypeVar

_type_fn = type

T = TypeVar("T")


# noinspection PyShadowingBuiltins
def import_value(
    ref: str,
    *,
    type: type[T],
    name: str,
    example: Optional[str] = None,
) -> T:
    """
    Dynamically import a value given by its reference `ref`.

    Args:
        ref: A value reference of the form "<module>:<attr>".
        type: Expected type of the reference
        name: Name of the reference
        example: An example reference (for error messages)

    Returns:
        The imported value.

    Raises:
        ValueError: if the `ref` syntax is invalid, or the module
            cannot be imported, or attribute cannot be found.
        TypeError: if the loaded value is not an instance of
            the expected type.
    """
    example = example or "path.to.module:attr"

    try:
        module_name, attr_ref = ref.split(":", maxsplit=1)
    except ValueError:
        raise ValueError(
            f"The {name} reference must be passed in the form {example!r}, "
            f"but got {ref!r}."
        )

    try:
        module = importlib.import_module(module_name)
    except ImportError:
        raise ValueError(f"Cannot import module {module_name!r}.")

    value = module
    partial_spec = module_name
    for i, attr_name in enumerate(attr_ref.split(".")):
        try:
            value = getattr(value, attr_ref)
        except AttributeError:
            raise ValueError(
                f"{'Module' if i == 0 else 'Object'} {partial_spec!r} "
                f"has no attribute {attr_name!r}."
            )
        partial_spec += (":" if i == 0 else ".") + attr_name

    if not isinstance(value, type):
        raise TypeError(
            f"The reference {ref!r} should refer to a {name} of type "
            f"{type.__name__}, but got type {_type_fn(value).__name__}."
        )

    return value
