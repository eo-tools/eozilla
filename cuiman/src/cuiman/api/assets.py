#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Asset recognition and notebook display utilities."""

import asyncio
import sys
from html import escape
from inspect import currentframe, iscoroutinefunction
from json import dumps
from math import asinh, floor, log2, pi, radians, tan
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
    properties = "".join(
        f"<dt>{escape(str(key))}</dt><dd>{escape(dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value))}</dd>"
        for key, value in item.properties.items()
        if key != "datetime" and value is not None
    )
    properties_html = (
        f"<dl class='cuiman-assets-properties'>{properties}</dl>" if properties else ""
    )

    asset_rows = []
    for key, asset in item.assets.items():
        if role_filter is not None and not role_filter.intersection(asset.roles or []):
            continue
        asset_rows.append(
            _render_asset(key, asset, expression_prefix=expression_prefix)
        )

    if asset_rows:
        assets_html = (
            "<div class='cuiman-assets-table'>"
            "<table>"
            "<thead><tr><th>Asset</th><th>File</th><th>Title</th>"
            "<th>Roles</th><th>Code</th>"
            "</tr></thead>"
            f"<tbody>{''.join(asset_rows)}</tbody>"
            "</table></div>"
        )
    else:
        assets_html = "<p class='cuiman-assets-empty'><em>No assets</em></p>"

    item_html = (
        "<style>"
        ".cuiman-assets-card{border-radius:12px;box-shadow:0 3px 12px #0001}"
        ".cuiman-assets-map{border-radius:8px}"
        ".cuiman-assets{font:14px/1.5 system-ui,sans-serif;color:inherit}"
        ".cuiman-assets header{padding:0;"
        "overflow-wrap:anywhere}"
        ".cuiman-assets header strong{font-size:20px;font-weight:650}"
        ".cuiman-assets-meta{opacity:.65;font-size:12px;margin-top:4px}"
        ".cuiman-assets-properties{display:grid;grid-template-columns:minmax(100px,auto) 1fr;"
        "gap:4px 16px;margin:14px 0 0;font-size:12px;max-height:180px;overflow:auto}"
        ".cuiman-assets-properties dt{opacity:.6;font-weight:400}"
        ".cuiman-assets-properties dd{margin:0;overflow-wrap:anywhere}"
        ".cuiman-assets-table{overflow-x:auto;padding:8px 20px 16px}"
        ".cuiman-assets table{width:100%;border-collapse:collapse;"
        "text-align:left;background:transparent}"
        ".cuiman-assets th{font-size:11px;text-transform:uppercase;"
        "letter-spacing:.06em;opacity:.6;font-weight:600;text-align:left}"
        ".cuiman-assets td,.cuiman-assets th{padding:10px 12px;"
        "border-bottom:1px solid #8882;text-align:left}"
        ".cuiman-assets td:first-child{font-weight:600}"
        ".cuiman-assets td:last-child{width:32px;text-align:center}"
        ".cuiman-assets tbody tr:last-child td{border-bottom:0}"
        ".cuiman-assets tbody tr:hover{background:#8881}"
        ".cuiman-assets a{color:#3b9fa5;text-decoration:none}"
        ".cuiman-assets a:hover{text-decoration:underline}"
        ".cuiman-assets-empty{padding:0 20px}"
        ".cuiman-assets-previews figure{margin:0;width:160px;min-width:0}"
        ".cuiman-assets-previews img{display:block;width:100%;"
        "height:140px;object-fit:contain;background:#8881;border-radius:8px}"
        ".cuiman-assets-previews figcaption{font:12px/1.5 system-ui,sans-serif;"
        "opacity:.65;padding:8px 2px}"
        "</style>"
        "<section class='cuiman-assets'>"
        f"<header><strong>{item_id}</strong>"
        f"<div class='cuiman-assets-meta'>{' · '.join(filter(None, (collection, datetime)))}</div>"
        f"{properties_html}"
        "</header>"
        f"{assets_html}</section>"
    )

    heading_html = item_html.replace(assets_html, "")
    map_widget = _render_geometry(item)
    if map_widget is not None:
        import ipywidgets as widgets

        preview_widget = (
            widgets.HBox(
                [
                    map_widget,
                    widgets.HTML(
                        value=previews_html,
                        layout=widgets.Layout(width="160px", min_width="0"),
                    ),
                ],
                layout=widgets.Layout(
                    flex_flow="row wrap",
                    gap="12px",
                ),
            )
            if previews_html
            else map_widget
        )
        heading = widgets.HBox(
            [
                widgets.HTML(
                    value=heading_html,
                    layout=widgets.Layout(flex="1 1 320px", min_width="0"),
                ),
                preview_widget,
            ],
            layout=widgets.Layout(
                width="100%",
                flex_flow="row wrap",
                align_items="flex-start",
                justify_content="space-between",
                padding="16px 20px 8px",
                gap="16px",
            ),
        )
        card = widgets.VBox(
            [
                heading,
                widgets.HTML(
                    value=f"<section class='cuiman-assets'>{assets_html}</section>"
                ),
            ],
            layout=widgets.Layout(
                width="100%",
                margin="12px 0 24px",
                border="1px solid #8884",
                overflow="hidden",
            ),
        )
        card.add_class("cuiman-assets-card")
        return card
    else:
        return HTML(
            "<div style='border:1px solid #8884;"
            "border-radius:12px;overflow:hidden;margin:12px 0 24px'>"
            + "<div style='display:flex;flex-wrap:wrap;gap:16px;padding:20px'>"
            + f"<div style='flex:1 1 320px;min-width:0'>{heading_html}</div>"
            + previews_html
            + "</div>"
            + f"<section class='cuiman-assets'>{assets_html}</section>"
            + "</div>"
        )


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
    geometry_bounds = _geometry_bounds(item.geometry) if item.geometry else None
    if geometry_bounds:
        west, south, east, north = geometry_bounds
    elif bbox and len(bbox) == 4:
        west, south, east, north = bbox
    elif bbox and len(bbox) == 6:
        west, south, east, north = bbox[0], bbox[1], bbox[3], bbox[4]
    else:
        return None

    map_widget = Map(
        center=[(south + north) / 2, (west + east) / 2],
        zoom=_geometry_zoom((west, south, east, north), 180, 140),
        scroll_wheel_zoom=False,
        layout=widgets.Layout(
            width="180px",
            height="140px",
            flex="0 0 180px",
            min_width="0",
            overflow="hidden",
        ),
    )
    map_widget.add_class("cuiman-assets-map")
    map_bounds = ((south, west), (north, east))

    if item.geometry:
        layer = GeoJSON(
            data={
                "type": "Feature",
                "geometry": item.geometry,
                "properties": {},
            },
            style={"color": "#0d9488", "weight": 2, "fillOpacity": 0.18},
        )
    else:
        layer = Rectangle(
            bounds=map_bounds,
            color="#0d9488",
            fill_opacity=0.18,
        )

    map_widget.add(layer)
    viewport = None

    def fit_viewport(change):
        # Pixel bounds arrive after display and on resize. Ignore pan/zoom
        # updates of the same size so users can still explore the map.
        nonlocal viewport
        (left, top), (right, bottom) = change["new"]
        size = (round(right - left), round(bottom - top))
        if min(size) > 64 and size != viewport:
            viewport = size
            map_widget.center = [(south + north) / 2, (west + east) / 2]
            map_widget.zoom = _geometry_zoom((west, south, east, north), *size)

    map_widget.observe(fit_viewport, names="pixel_bounds")
    return map_widget


def _geometry_zoom(bounds, width, height):
    """Fit Web Mercator bounds into a viewport with 24px padding on each side."""
    west, south, east, north = bounds

    def mercator_y(latitude):
        return asinh(tan(radians(max(-85.05112878, min(85.05112878, latitude)))))

    x_span = max(abs(east - west) / 360, 1e-12)
    y_span = max(abs(mercator_y(north) - mercator_y(south)) / (2 * pi), 1e-12)
    scale = min(
        max(width - 48, 1) / (256 * x_span), max(height - 48, 1) / (256 * y_span)
    )
    return max(0, min(16, floor(log2(scale))))


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
                "<figure style='max-width:100%'>"
                f"{preview}<figcaption>{caption}</figcaption></figure>"
            )
    return (
        f"<div class='cuiman-assets-previews' style='display:flex;flex-wrap:wrap;gap:16px'>{''.join(previews)}</div>"
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
