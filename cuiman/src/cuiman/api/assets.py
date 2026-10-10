#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Asset recognition and notebook display utilities."""

import asyncio
import sys
from html import escape
from inspect import currentframe, iscoroutinefunction
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, Iterable, Sequence
from urllib.parse import unquote, urlsplit

if TYPE_CHECKING:
    from pystac import Asset, Item, ItemCollection


def as_stac_asset(value: Any) -> "Asset | None":
    """Return the value if it is a native PySTAC Asset, otherwise return None.

    Inspect only an already loaded PySTAC module so ordinary result opening
    does not import this optional dependency.
    """
    module = sys.modules.get("pystac")
    asset_type = getattr(module, "Asset", None)
    return value if asset_type is not None and isinstance(value, asset_type) else None


async def display_assets(
    items: "Item | Sequence[Item] | ItemCollection",
    *,
    roles: str | Iterable[str] | None = None,
    previews: bool = True,
    open_asset: "Callable[[Asset], Any] | None" = None,
) -> None:
    """Render grouped STAC items and assets, with optional ipyleaflet previews.

    Args:
        items: The STAC item or items to display.
        roles: Show assets matching any of these roles. A string matches one
            role, None shows all assets, and an empty iterable matches none.
        previews: Open and display thumbnail, overview, and visual assets.
            Set to ``False`` to prevent asset preview reads. Geometry previews
            remain enabled. Asset previews are independent of the table's
            role filter; unreadable or unsupported previews are skipped.
        open_asset: A synchronous or asynchronous asset opener. If omitted,
            asset previews are skipped; tables and geometry maps remain enabled.
    """
    await _display_assets(
        items,
        expression=_get_items_expression("display_assets"),
        roles=roles,
        previews=previews,
        open_asset=open_asset,
    )


async def _display_assets(
    items: "Item | Sequence[Item] | ItemCollection",
    *,
    expression: str | None,
    roles: str | Iterable[str] | None = None,
    previews: bool = True,
    open_asset: "Callable[[Asset], Any] | None" = None,
) -> None:
    """Display items with the expression captured before entering client bridges."""

    from IPython.display import display
    from pystac import Item, ItemCollection

    role_filter = (
        None if roles is None else {roles} if isinstance(roles, str) else set(roles)
    )

    if isinstance(items, Item):
        item_list = [items]

        def expression_prefix_for(i):
            return f"{expression or 'item'}"
    elif isinstance(items, ItemCollection):
        item_list = list(items.items)

        def expression_prefix_for(i):
            return f"{expression or 'item_collection'}.items[{i}]"
    else:
        msg = (
            "items must be a pystac.Item or "
            "Sequence[pystac.Item] or pystac.ItemCollection"
        )
        try:
            item_list = list(items)
        except Exception as e:
            raise TypeError(msg) from e

        for item in item_list:
            if not isinstance(item, Item):
                raise TypeError(msg)

        def expression_prefix_for(i):
            return f"{expression or 'items'}[{i}]"

    for item_index, item in enumerate(item_list):
        previews_html = (
            await _load_previews(item, open_asset=open_asset)
            if previews and open_asset is not None
            else ""
        )
        display(
            _render_item(
                item,
                role_filter=role_filter,
                expression_prefix=expression_prefix_for(item_index),
                previews_html=previews_html,
            )
        )


def _render_item(
    item: "Item",
    *,
    role_filter: set[str] | None = None,
    expression_prefix: str = "",
    previews_html: str = "",
):
    """Assemble the item table, geometry map, and optional asset previews."""

    from IPython.display import HTML

    item_id = escape(str(item.id))
    collection = escape(str(item.collection_id or ""))
    datetime = escape(str(item.properties.get("datetime") or ""))

    asset_rows = []
    for key, asset in item.assets.items():
        if role_filter is not None and not role_filter.intersection(asset.roles or []):
            continue
        asset_rows.append(
            _render_asset(key, asset, expression_prefix=expression_prefix)
        )

    if asset_rows:
        assets_html = (
            "<div style='margin:0.5em 0 0.5em 1.5em'>"
            "<table style='border-collapse:collapse;width:100%'>"
            "<thead><tr><th>Asset</th><th>File</th><th>Title</th>"
            "<th>Roles</th><th>Code</th>"
            "</tr></thead>"
            f"<tbody>{''.join(asset_rows)}</tbody>"
            "</table></div>"
        )
    else:
        assets_html = "<div style='margin-left:1.5em'><em>No assets</em></div>"

    item_html = (
        "<section style='margin:1em 0;padding:0.75em;"
        "border:1px solid #888;border-radius:0.4em'>"
        f"<div><strong>{item_id}</strong></div>"
        f"<div style='opacity:0.75'>{collection} · {datetime}</div>"
        f"{assets_html}</section>"
    )

    map_widget = _render_geometry(item)
    if map_widget is not None:
        import ipywidgets as widgets

        preview_widget = (
            widgets.HBox(
                [map_widget, widgets.HTML(value=previews_html)],
                layout=widgets.Layout(width="100%", flex_flow="row wrap"),
            )
            if previews_html
            else map_widget
        )
        return widgets.VBox(
            [widgets.HTML(value=item_html), preview_widget],
            layout=widgets.Layout(width="100%"),
        )
    else:
        return HTML(item_html + previews_html)


def _geometry_bounds(geometry):
    """Get [west, south, east, north] from GeoJSON coordinates."""
    positions = []

    def visit(value):
        if isinstance(value, (list, tuple)):
            if (
                len(value) >= 2
                and isinstance(value[0], (int, float))
                and isinstance(value[1], (int, float))
            ):
                positions.append((value[0], value[1]))
            else:
                for child in value:
                    visit(child)

    if geometry.get("type") == "GeometryCollection":
        for child in geometry.get("geometries", []):
            bounds = _geometry_bounds(child)
            if bounds:
                positions.extend(((bounds[0], bounds[1]), (bounds[2], bounds[3])))
    else:
        visit(geometry.get("coordinates", []))

    if not positions:
        return None

    longitudes, latitudes = zip(*positions, strict=False)
    return (
        min(longitudes),
        min(latitudes),
        max(longitudes),
        max(latitudes),
    )


def _render_geometry(item: "Item"):
    """Build an optional geometry map from an item's bounds or coordinates."""
    try:
        import ipywidgets as widgets
        from ipyleaflet import GeoJSON, Map, Rectangle  # type: ignore[import-not-found]
    except ImportError:
        return None

    bbox = item.bbox
    if bbox and len(bbox) == 4:
        west, south, east, north = bbox
    elif bbox and len(bbox) == 6:
        west, south, east, north = bbox[0], bbox[1], bbox[3], bbox[4]
    elif item.geometry:
        bounds = _geometry_bounds(item.geometry)
        if not bounds:
            return None
        west, south, east, north = bounds
    else:
        return None

    map_widget = Map(
        center=[(south + north) / 2, (west + east) / 2],
        zoom=2,
        scroll_wheel_zoom=False,
        layout=widgets.Layout(width="360px", height="240px"),
    )
    map_bounds = ((south, west), (north, east))

    if item.geometry:
        layer = GeoJSON(
            data={
                "type": "Feature",
                "geometry": item.geometry,
                "properties": {},
            },
            style={"color": "#d62728", "fillOpacity": 0.15},
        )
    else:
        layer = Rectangle(
            bounds=map_bounds,
            color="#d62728",
            fill_opacity=0.15,
        )

    map_widget.add_layer(layer)
    map_widget.fit_bounds(map_bounds)
    return map_widget


async def _load_previews(item: "Item", *, open_asset: "Callable[[Asset], Any]") -> str:
    """Load captioned previews for the item's viewable preview assets."""
    previews = []
    for key, asset in item.assets.items():
        if not {"thumbnail", "overview", "visual"}.intersection(asset.roles or []):
            continue
        preview = await _load_preview(asset, open_asset=open_asset)
        if preview is not None:
            caption = escape(str(asset.title or key))
            previews.append(
                "<figure style='margin:0;max-width:360px'>"
                f"{preview}<figcaption>{caption}</figcaption></figure>"
            )
    return (
        f"<div style='display:flex;flex-wrap:wrap;gap:0.75em'>{''.join(previews)}</div>"
        if previews
        else ""
    )


async def _load_preview(
    asset: "Asset", *, open_asset: "Callable[[Asset], Any]"
) -> str | None:
    """Open, render, and close one preview using the supplied reader."""
    try:
        if iscoroutinefunction(open_asset):
            value = await open_asset(asset)
        else:
            value = await asyncio.to_thread(open_asset, asset)
        try:
            return _render_preview(value)
        finally:
            close = getattr(value, "close", None)
            if callable(close):
                close()
    except Exception:
        # Previews are best-effort: a broken asset must not hide the item table.
        return None


def _render_preview(value: Any) -> str | None:
    """Embed an opened value's HTML or image representation without I/O."""
    from base64 import b64encode

    from IPython.core.formatters import DisplayFormatter

    data, _ = DisplayFormatter().format(
        value,
        include=["text/html", "image/png", "image/jpeg", "image/svg+xml"],
    )
    if data.get("text/html"):
        return data["text/html"]
    for media_type in ("image/png", "image/jpeg", "image/svg+xml"):
        image = data.get(media_type)
        if not image:
            continue
        if media_type == "image/svg+xml":
            image = b64encode(image.encode("utf-8")).decode("ascii")
        elif isinstance(image, bytes):
            image = b64encode(image).decode("ascii")
        return (
            f"<img src='data:{media_type};base64,{escape(image, quote=True)}' "
            "alt='Asset preview' style='max-width:360px;max-height:240px;"
            "object-fit:contain'>"
        )
    return None


def _render_asset(
    key: str,
    asset: "Asset",
    *,
    expression_prefix: str = "",
) -> str:
    """Render an escaped asset row with a file link, roles, and copy button."""

    href = str(asset.href)
    path = urlsplit(href.replace("\\", "/")).path.rstrip("/")
    filename = unquote(path.rsplit("/", 1)[-1]) or href
    scheme = urlsplit(href).scheme.lower()

    if scheme in ("", "http", "https", "file"):
        file_html = (
            f"<a href='{escape(href, quote=True)}' "
            "style='overflow-wrap:anywhere'>"
            f"{escape(filename)}</a>"
        )
    else:
        file_html = escape(filename)

    expression = f"{expression_prefix}.assets[{key!r}]"
    title = escape(str(asset.title or ""))
    roles_html = escape(", ".join(asset.roles or []))

    return (
        "<tr>"
        f"<td>{escape(str(key))}</td>"
        f"<td>{file_html}</td>"
        f"<td>{title}</td>"
        f"<td>{roles_html}</td>"
        "<td>"
        f"<button data-copy='{escape(expression, quote=True)}' "
        "type='button' title='Copy expression' aria-label='Copy expression' "
        "style='background:transparent;border:0;padding:0.25em;"
        "color:inherit;cursor:pointer;line-height:0' "
        'onclick="(async b => {'
        "try { await navigator.clipboard.writeText(b.dataset.copy); "
        "b.title = 'Copied'; } "
        "catch (_) { window.prompt('Copy expression:', b.dataset.copy); }"
        '})(this)">'
        "<svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' "
        "viewBox='0 0 24 24' fill='none' stroke='currentColor' "
        "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' "
        "aria-hidden='true' focusable='false'>"
        "<rect x='9' y='9' width='13' height='13' rx='2'/>"
        "<path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9"
        "a2 2 0 0 1 2 2v1'/></svg></button>"
        "</td>"
        "</tr>"
    )


def _get_items_expression(function_name: str = "show_assets") -> str | None:
    """Capture the public caller's items expression without retaining its frame."""
    frame = currentframe()
    try:
        caller = frame.f_back.f_back if frame and frame.f_back else None
        expression = _get_call_argument_source(caller, function_name)
    finally:
        del frame
    if expression is None:
        return None

    import ast

    node = ast.parse(f"({expression})", mode="eval").body
    # Attribute access binds correctly to these expressions without parentheses.
    return (
        expression
        if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript, ast.Call))
        else f"({expression})"
    )


def _get_call_argument_source(
    frame: FrameType | None, function_name: str
) -> str | None:
    """Recover the items argument from the caller's cached source, without eval.

    Instruction positions distinguish calls on the same line and aliases.
    When positions are unavailable, accept only one matching named call.
    Missing source and ambiguous calls return None.
    """
    import ast
    import dis
    import linecache

    if frame is None:
        return None
    source = "".join(linecache.getlines(frame.f_code.co_filename, frame.f_globals))
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    positions = next(
        (
            instruction.positions
            for instruction in dis.get_instructions(frame.f_code, show_caches=True)
            if instruction.offset == frame.f_lasti
        ),
        None,
    )
    position_span = (
        tuple(positions)
        if positions is not None and all(value is not None for value in positions)
        else None
    )
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Call, ast.Await)):
            continue
        call = node.value if isinstance(node, ast.Await) else node
        if not isinstance(call, ast.Call):
            continue
        if position_span is not None:
            span = (node.lineno, node.end_lineno, node.col_offset, node.end_col_offset)
            if span != position_span:
                continue
        else:
            if not isinstance(node, ast.Call):
                continue
            name = (
                call.func.id
                if isinstance(call.func, ast.Name)
                else call.func.attr
                if isinstance(call.func, ast.Attribute)
                else None
            )
            if name != function_name or not (
                node.lineno <= frame.f_lineno <= (node.end_lineno or node.lineno)
            ):
                continue
        candidates.append(call)

    if len(candidates) != 1:
        return None
    call = candidates[0]
    argument = (
        call.args[0]
        if call.args
        else next((kw.value for kw in call.keywords if kw.arg == "items"), None)
    )
    if argument is None or isinstance(argument, ast.Starred):
        return None
    return ast.get_source_segment(source, argument)
