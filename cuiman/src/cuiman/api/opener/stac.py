#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""STAC-related utilities for notebook display."""

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from pystac import Item, ItemCollection


def show_assets(items: "Item | Sequence[Item] | ItemCollection") -> None:
    """Render grouped STAC items and assets, with optional ipyleaflet previews."""

    from html import escape
    from urllib.parse import unquote, urlsplit

    from IPython.display import HTML, display
    from pystac import Item, ItemCollection

    try:
        import ipywidgets as widgets
        from ipyleaflet import GeoJSON, Map, Rectangle  # type: ignore[import-not-found]
    except ImportError:
        widgets = None
        GeoJSON = Map = Rectangle = None

    if isinstance(items, Item):
        item_list = [items]

        def expression_for(i, key):
            return f".assets[{key!r}]"
    elif isinstance(items, ItemCollection):
        item_list = list(items.items)

        def expression_for(i, key):
            return f".items[{i}].assets[{key!r}]"
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

        def expression_for(i, key):
            return f"[{i}].assets[{key!r}]"

    def geometry_bounds(geometry):
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
                bounds = geometry_bounds(child)
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

    def make_map(item):
        if Map is None:
            return None

        assert Map is not None
        assert GeoJSON is not None
        assert Rectangle is not None

        bbox = item.bbox
        if bbox and len(bbox) == 4:
            west, south, east, north = bbox
        elif bbox and len(bbox) == 6:
            west, south, east, north = bbox[0], bbox[1], bbox[3], bbox[4]
        elif item.geometry:
            bounds = geometry_bounds(item.geometry)
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

    for item_index, item in enumerate(item_list):
        item_id = escape(str(item.id))
        collection = escape(str(item.collection_id or ""))
        datetime = escape(str(item.properties.get("datetime") or ""))

        asset_rows = []
        for key, asset in item.assets.items():
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

            expression = expression_for(item_index, key)
            title = escape(str(asset.title or ""))

            asset_rows.append(
                "<tr>"
                f"<td>{escape(str(key))}</td>"
                f"<td>{file_html}</td>"
                f"<td>{title}</td>"
                "<td>"
                f"<button data-copy='{escape(expression, quote=True)}' "
                'onclick="(async b => {'
                "try { await navigator.clipboard.writeText(b.dataset.copy); "
                "b.title = 'Copied'; } "
                "catch (_) { window.prompt('Copy expression:', b.dataset.copy); }"
                '})(this)">Copy</button>'
                "</td>"
                "</tr>"
            )

        if asset_rows:
            assets_html = (
                "<div style='margin:0.5em 0 0.5em 1.5em'>"
                "<table style='border-collapse:collapse;width:100%'>"
                "<thead><tr><th>Asset</th><th>File</th><th>Title</th><th></th>"
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

        map_widget = make_map(item)
        if map_widget is not None:
            display(
                widgets.VBox(
                    [widgets.HTML(value=item_html), map_widget],
                    layout=widgets.Layout(width="100%"),
                )
            )
        else:
            display(HTML(item_html))
