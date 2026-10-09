# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Compose native STAC opening with application-owned transformations."""

from copy import deepcopy
from inspect import isawaitable
from typing import Any, Awaitable, Callable

from ...context import JobResultOpenContext
from ...errors import StacJobResultOpenError
from ...opener import JobResultOpener, assert_opener_type_valid

StacTransform = Callable[[Any, JobResultOpenContext], Awaitable[Any]]
"""An asynchronous transformation of one independently copied STAC result."""


def compose_stac_opener(
    base_opener: type[JobResultOpener],
    *,
    transformers: tuple[StacTransform, ...],
    accepts: Callable[[JobResultOpenContext], bool | Awaitable[bool]] | None = None,
) -> type[JobResultOpener]:
    """Return a registerable opener that parses once and transforms in order.

    ``base_opener`` supplies STAC acceptance, parsing, and optional dependency
    behavior. The application owns the predicate, transformations, and any
    configuration captured by them. No global registry is changed here.
    """
    assert_opener_type_valid(base_opener)
    chain = tuple(transformers)
    if not chain or any(not callable(transform) for transform in chain):
        raise TypeError("STAC composition requires callable transformers")
    if accepts is not None and not callable(accepts):
        raise TypeError("STAC acceptance predicate must be callable")

    class ComposedStacOpener(JobResultOpener):
        """Delegate parsing to the base opener and apply an isolated chain."""

        def __init__(self) -> None:
            self._base = base_opener()
            self._predicate_error: str | None = None

        @classmethod
        def is_usable(cls) -> bool:
            """Use the base opener's optional dependency check."""
            return base_opener.is_usable()

        @classmethod
        def _unavailable_error(cls, ctx: JobResultOpenContext) -> Exception | None:
            return base_opener._unavailable_error(ctx)

        async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
            """Check the source predicate and base acceptance without parsing."""
            if accepts is not None:
                try:
                    selected = accepts(ctx)
                    if isawaitable(selected):
                        selected = await selected
                    if not selected:
                        return False
                except Exception as error:
                    self._predicate_error = type(error).__name__
            return await self._base.accept_job_result(ctx)

        async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
            """Parse once, then pass independent copies through each stage."""
            if self._predicate_error is not None:
                raise StacJobResultOpenError(
                    f"STAC composition predicate failed ({self._predicate_error})"
                )
            result = await self._base.open_job_result(ctx)
            for transform in chain:
                try:
                    candidate = await transform(deepcopy(result), ctx)
                    _validate_transformed(candidate, ctx.data_type)
                except Exception as error:
                    raise StacJobResultOpenError(
                        f"STAC transformation failed ({type(error).__name__})"
                    ) from None
                result = candidate
            return result

    ComposedStacOpener.__name__ = f"Composed{base_opener.__name__}"
    return ComposedStacOpener


def _validate_transformed(value: Any, requested_type: type | None) -> None:
    import pystac

    if not isinstance(value, (pystac.Item, pystac.ItemCollection, pystac.Catalog)):
        raise StacJobResultOpenError("Transformation must return native STAC metadata")
    if requested_type is not None and not isinstance(value, requested_type):
        raise StacJobResultOpenError("Transformation changed the requested STAC type")
    loaded: list[Any] = (
        list(value.items) if isinstance(value, pystac.ItemCollection) else [value]
    )
    seen: set[int] = set()
    while loaded:
        node = loaded.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        for asset in getattr(node, "assets", {}).values():
            if not isinstance(asset, pystac.Asset) or asset.owner is not node:
                raise StacJobResultOpenError("Transformed Asset ownership is invalid")
        for link in getattr(node, "links", []):
            target = getattr(link, "_target_object", None)
            if isinstance(target, pystac.STACObject):
                loaded.append(target)
