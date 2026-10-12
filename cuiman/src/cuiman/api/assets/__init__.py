#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Notebook display utilities for STAC assets and job results."""

from typing import TYPE_CHECKING, Any, Callable, Iterable, Sequence

from gavicore.models.core import JobResults, QualifiedValue

from .common import _get_items_expression
from .stac import as_stac_asset

if TYPE_CHECKING:
    from pystac import Asset, Item, ItemCollection

__all__ = ["as_stac_asset", "display_assets"]


async def display_assets(
    items: "JobResults | QualifiedValue | dict[str, Any] | Item | Sequence[Item] | ItemCollection",
    *,
    roles: str | Iterable[str] | None = None,
    previews: bool = True,
    open_asset: "Callable[[Asset], Any] | None" = None,
) -> None:
    """Render job result tables or grouped STAC assets and optional previews.

    Args:
        items: JobResults, STAC objects, or inline STAC JSON dictionaries
            (optionally wrapped in QualifiedValue).
        roles: Show assets matching any of these roles. A string matches one
            role, None shows all assets, and an empty iterable matches none.
            Job result rows are not filtered by roles.
        previews: Open and display thumbnail, overview, and visual assets.
            Set to ``False`` to prevent asset preview reads. Geometry previews
            remain enabled. Asset previews are independent of the table's
            role filter; unreadable or unsupported previews are skipped.
        open_asset: A synchronous or asynchronous asset opener. If omitted,
            asset previews are skipped; tables and geometry maps remain enabled.
            Job result tables never open linked outputs.
    """
    await _display_assets(
        items,
        expression=_get_items_expression("display_assets"),
        roles=roles,
        previews=previews,
        open_asset=open_asset,
    )


async def _display_assets(
    items: "JobResults | QualifiedValue | dict[str, Any] | Item | Sequence[Item] | ItemCollection",
    *,
    expression: str | None,
    roles: str | Iterable[str] | None = None,
    previews: bool = True,
    open_asset: "Callable[[Asset], Any] | None" = None,
) -> None:
    """Dispatch notebook display without importing optional STAC dependencies."""
    if isinstance(items, JobResults):
        from IPython.display import display

        from .job_results import _render_job_results

        display(_render_job_results(items, expression=expression))
    else:
        from .stac import _display_stac_assets

        await _display_stac_assets(
            items,
            expression=expression,
            roles=roles,
            previews=previews,
            open_asset=open_asset,
        )
