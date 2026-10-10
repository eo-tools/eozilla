#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import subprocess
import sys
from datetime import datetime, timezone
from html import unescape
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pystac import Asset, Item, ItemCollection

from cuiman.api import AsyncClient, Client, ClientConfig
from cuiman.api.opener import JobResultOpener
from cuiman.api.assets import (
    as_stac_asset,
    _load_preview,
    display_assets,
    _render_asset,
    _render_geometry,
    _render_item,
    _render_preview,
    _geometry_zoom,
)
from gavicore.util.runsync import run_sync


def show_assets(items, **kwargs):
    class Config(ClientConfig):
        pass

    client = Client(
        config_type=Config,
        api_url="https://process.test",
        auth={"auth_type": "none"},
    )
    try:
        return client.show_assets(items, **kwargs)
    finally:
        client.close()


def new_item():
    return Item("example", None, None, datetime(2026, 10, 10, tzinfo=timezone.utc), {})


def test_as_stac_asset_returns_native_asset():
    asset = Asset("result.png")
    assert as_stac_asset(asset) is asset


@pytest.mark.parametrize("value", [None, {}, "result.png"])
def test_as_stac_asset_rejects_other_values(value):
    assert as_stac_asset(value) is None


@pytest.mark.parametrize("module_state", ["absent", "blocked", "without_asset"])
def test_as_stac_asset_does_not_import_pystac(monkeypatch, module_state):
    asset = Asset("result.png")
    if module_state == "absent":
        monkeypatch.delitem(sys.modules, "pystac")
    else:
        monkeypatch.setitem(
            sys.modules,
            "pystac",
            None if module_state == "blocked" else SimpleNamespace(),
        )

    assert as_stac_asset(asset) is None
    if module_state == "absent":
        assert "pystac" not in sys.modules


@pytest.fixture
def displayed(monkeypatch):
    outputs = []
    monkeypatch.setattr("IPython.display.display", outputs.append)
    monkeypatch.setitem(sys.modules, "ipyleaflet", None)
    return outputs


def test_render_item_builds_display_without_displaying(displayed):
    item = new_item()
    item.add_asset("result", Asset("result.csv", roles=["data"]))

    rendered = _render_item(item)

    assert "<strong>example</strong>" in rendered.data
    assert "<td>result</td>" in rendered.data
    assert ".assets['result']" in unescape(rendered.data)
    assert displayed == []


@pytest.mark.asyncio
@pytest.mark.parametrize("previews", [False, True])
@pytest.mark.parametrize("with_map", [False, True])
async def test_standalone_without_opener_keeps_table_and_geometry(
    displayed, map_modules, monkeypatch, previews, with_map
):
    widgets, leaflet = map_modules
    item = new_item()
    if with_map:
        item.bbox = [1, 2, 3, 4]
    item.add_asset("preview", Asset("missing.png", roles=["thumbnail"]))
    load_preview = AsyncMock()
    monkeypatch.setattr("cuiman.api.assets._load_preview", load_preview)

    assert await display_assets(item, previews=previews) is None

    load_preview.assert_not_called()
    assert leaflet.Map.called is with_map
    assert widgets.HBox.called is with_map
    html = widgets.HTML.call_args.kwargs["value"] if with_map else displayed[0].data
    assert "<td>preview</td>" in html
    assert "<figure " not in html


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("previews", [False, True])
async def test_standalone_uses_optional_opener(displayed, asynchronous, previews):
    from IPython.display import HTML

    item = new_item()
    asset = Asset("missing.png", roles=["thumbnail"])
    item.add_asset("preview", asset)
    mock_type = AsyncMock if asynchronous else MagicMock
    open_asset = mock_type(return_value=HTML("<p>Supplied preview</p>"))

    await display_assets(item, open_asset=open_asset, previews=previews)

    assert open_asset.call_count == int(previews)
    if previews:
        open_asset.assert_called_once_with(asset)
        if asynchronous:
            open_asset.assert_awaited_once_with(asset)
    assert ("<p>Supplied preview</p>" in displayed[0].data) is previews


def test_render_item_accepts_loaded_previews(displayed):
    rendered = _render_item(new_item(), previews_html="<p>Loaded preview</p>")

    assert "<p>Loaded preview</p>" in rendered.data
    assert displayed == []


def test_item_properties_are_visible_and_escaped(displayed):
    item = new_item()
    item.properties.update(
        {
            "eo:cloud_cover": 0,
            "approved": False,
            "<sensor>": {"name": "<value>"},
            "missing": None,
        }
    )
    html = _render_item(item).data
    assert "<dt>eo:cloud_cover</dt><dd>0</dd>" in html
    assert "<dt>approved</dt><dd>False</dd>" in html
    assert "<dt>&lt;sensor&gt;</dt>" in html
    assert "&lt;value&gt;" in html
    assert "<dt>missing</dt>" not in html
    assert "<dt>datetime</dt>" not in html


def test_render_asset_builds_row_without_displaying(displayed):
    asset = Asset("result.csv", title="Result", roles=["data", "metadata"])

    html = _render_asset("result", asset, expression_prefix="[2]")

    assert html.startswith("<tr>") and html.endswith("</tr>")
    assert "<td>result</td>" in html
    assert "<td>Result</td>" in html
    assert "<td>data, metadata</td>" in html
    assert "[2].assets['result']" in unescape(html)
    assert displayed == []


def test_import_without_optional_pystac():
    completed = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['pystac'] = None; "
            "from cuiman.api import AsyncClient, Client; "
            "from cuiman.api.assets import "
            "as_stac_asset, _render_asset, _render_geometry, _render_item, _load_previews; "
            "assert as_stac_asset({}) is None; "
            "assert all(map(callable, "
            "(Client.show_assets, AsyncClient.show_assets, _render_item, _render_asset, _render_geometry, _load_previews)))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_assets_module_import_does_not_require_notebook_display(monkeypatch):
    import importlib

    from cuiman.api import assets

    monkeypatch.setitem(sys.modules, "IPython", None)
    monkeypatch.setitem(sys.modules, "IPython.display", None)

    importlib.reload(assets)

    assert assets.as_stac_asset({}) is None
    assert callable(assets.display_assets)


@pytest.mark.parametrize("roles", [None, [], ["data"], ["data", "metadata"]])
def test_asset_columns_and_copy_icon(displayed, roles):
    item = new_item()
    item.add_asset("result", Asset("https://example.invalid/result.csv", roles=roles))

    assert show_assets(item) is None

    html = displayed[0].data
    assert (
        "<th>Asset</th><th>File</th><th>Title</th><th>Roles</th><th>Code</th>" in html
    )
    assert f"<td>{', '.join(roles or [])}</td>" in html
    assert "<svg " in html
    assert "stroke='currentColor'" in html
    assert "aria-hidden='true'" in html
    assert "aria-label='Copy expression'" in html
    assert "title='Copy expression'" in html
    assert "type='button'" in html
    assert ">Copy</button>" not in html
    assert "navigator.clipboard.writeText(b.dataset.copy)" in html
    assert "window.prompt('Copy expression:', b.dataset.copy)" in html


@pytest.mark.parametrize("kind", ["item", "sequence", "collection"])
def test_copy_expressions(displayed, kind):
    key = "a'\"<&"
    item = new_item()
    item.add_asset(key, Asset("missing.csv"))
    if kind == "item":
        items = item
        prefix = "items"
    elif kind == "sequence":
        items = [new_item(), item]
        prefix = "items[1]"
    else:
        items = ItemCollection([new_item(), item])
        prefix = "items.items[1]"

    show_assets(items)

    html = displayed[-1].data
    assert f"data-copy='{prefix}.assets[{key!r}]'" in unescape(html)
    assert key not in html


def test_metadata_is_escaped(displayed):
    item = new_item()
    item.id = "<item>"
    item.collection_id = "<collection>"
    item.add_asset(
        "<asset>",
        Asset(
            "https://example.invalid/a%3Cb%3E.csv?x='&y=1",
            title="<title>",
            roles=["data", "<metadata>"],
        ),
    )

    show_assets(item)

    html = displayed[0].data
    for value in ("item", "collection", "asset", "title", "metadata"):
        assert f"<{value}>" not in html
        assert f"&lt;{value}&gt;" in html
    assert "data, &lt;metadata&gt;" in html
    assert "a&lt;b&gt;.csv</a>" in html
    assert "?x=&#x27;&amp;y=1'" in html


@pytest.mark.parametrize(
    "href, filename, linked",
    [
        ("missing.csv", "missing.csv", True),
        ("https://example.invalid/missing%20file.csv", "missing file.csv", True),
        ("file:///missing.csv", "missing.csv", True),
        ("s3://bucket/missing.csv", "missing.csv", False),
        ("javascript:alert(1)", "alert(1)", False),
        ("https://example.invalid", "https://example.invalid", True),
    ],
)
def test_asset_links_do_not_require_existing_files(displayed, href, filename, linked):
    item = new_item()
    item.add_asset("result", Asset(href))

    show_assets(item)

    html = displayed[0].data
    assert filename in html
    assert ("<a href=" in html) is linked


def test_empty_items_and_assets(displayed):
    show_assets([])
    assert displayed == []

    show_assets(new_item())
    assert "No assets" in displayed[0].data
    assert "<table" not in displayed[0].data


@pytest.mark.parametrize(
    "roles, expected",
    [
        (None, {"data", "metadata", "both", "unassigned", "empty"}),
        ("data", {"data", "both"}),
        (["metadata"], {"metadata", "both"}),
        (("data", "metadata"), {"data", "metadata", "both"}),
        ({"metadata", "unknown"}, {"metadata", "both"}),
        ([], set()),
        ("unknown", set()),
        ("Data", set()),
        ("dat", set()),
    ],
)
def test_role_filter(displayed, roles, expected):
    item = new_item()
    asset_roles = {
        "data": ["data"],
        "metadata": ["metadata"],
        "both": ["data", "metadata"],
        "unassigned": None,
        "empty": [],
    }
    for key, values in asset_roles.items():
        item.add_asset(key, Asset(f"{key}.csv", roles=values))

    show_assets(item, roles=roles)

    html = displayed[0].data
    for key in asset_roles:
        assert (f"<td>{key}</td>" in html) is (key in expected)
    if not expected:
        assert "No assets" in html
    assert item.assets.keys() == asset_roles.keys()
    assert {key: asset.roles for key, asset in item.assets.items()} == asset_roles


@pytest.mark.parametrize("kind", ["sequence", "collection"])
def test_role_generator_applies_to_all_items(displayed, kind):
    items = [new_item(), new_item()]
    for item in items:
        item.add_asset("result", Asset("result.csv", roles=["data"]))
        item.add_asset("manifest", Asset("manifest.xml", roles=["metadata"]))
    source = ItemCollection(items) if kind == "collection" else items

    show_assets(source, roles=(role for role in ["data"]))

    assert len(displayed) == 2
    for index, output in enumerate(displayed):
        html = output.data
        assert "<td>result</td>" in html
        assert "<td>manifest</td>" not in html
        prefix = ".items" if kind == "collection" else ""
        assert f"{prefix}[{index}].assets['result']" in unescape(html)


@pytest.mark.parametrize("items", [None, 42, ["not an item"]])
def test_invalid_items(displayed, items):
    with pytest.raises(TypeError, match="items must be a pystac.Item"):
        show_assets(items)
    assert displayed == []


@pytest.fixture
def map_modules(monkeypatch, displayed):
    widgets = SimpleNamespace(
        Layout=MagicMock(), HTML=MagicMock(), VBox=MagicMock(), HBox=MagicMock()
    )
    leaflet = SimpleNamespace(
        Map=MagicMock(), GeoJSON=MagicMock(), Rectangle=MagicMock()
    )
    monkeypatch.setitem(sys.modules, "ipywidgets", widgets)
    monkeypatch.setitem(sys.modules, "ipyleaflet", leaflet)
    return widgets, leaflet


@pytest.mark.parametrize(
    "bbox, geometry, expected_bounds",
    [
        ([1, 2, 3, 4], None, ((2, 1), (4, 3))),
        ([1, 2, 0, 3, 4, 10], None, ((2, 1), (4, 3))),
        (None, {"type": "Point", "coordinates": [1, 2]}, ((2, 1), (2, 1))),
        (
            None,
            {"type": "Polygon", "coordinates": [[[1, 2], [3, 4], [1, 2]]]},
            ((2, 1), (4, 3)),
        ),
        (
            None,
            {
                "type": "GeometryCollection",
                "geometries": [
                    {"type": "Point", "coordinates": [1, 2]},
                    {"type": "Point", "coordinates": [3, 4]},
                    {"type": "Point", "coordinates": []},
                ],
            },
            ((2, 1), (4, 3)),
        ),
    ],
)
def test_render_geometry(displayed, map_modules, bbox, geometry, expected_bounds):
    _, leaflet = map_modules
    item = new_item()
    item.bbox = bbox
    item.geometry = geometry

    rendered = _render_geometry(item)

    south_west, north_east = expected_bounds
    assert leaflet.Map.call_args.kwargs["center"] == [
        (south_west[0] + north_east[0]) / 2,
        (south_west[1] + north_east[1]) / 2,
    ]
    assert leaflet.Map.call_args.kwargs["zoom"] == _geometry_zoom(
        (south_west[1], south_west[0], north_east[1], north_east[0]), 180, 140
    )
    leaflet.Map.return_value.fit_bounds.assert_not_called()
    layer = leaflet.GeoJSON if geometry else leaflet.Rectangle
    leaflet.Map.return_value.add.assert_called_once_with(layer.return_value)
    if geometry:
        assert layer.call_args.kwargs["data"]["geometry"] == geometry
    else:
        assert layer.call_args.kwargs["bounds"] == expected_bounds
    assert rendered is leaflet.Map.return_value
    assert displayed == []


def test_geometry_viewport_fits_on_display_and_resize(map_modules):
    _, leaflet = map_modules
    item = new_item()
    item.bbox = [10, 50, 11, 51]
    widget = _render_geometry(item)
    fit = widget.observe.call_args.args[0]
    widget.observe.assert_called_once_with(fit, names="pixel_bounds")

    fit({"new": ((0, 0), (0, 0))})  # Not yet displayed.
    fit({"new": ((100, 200), (500, 480))})
    assert widget.zoom == _geometry_zoom(item.bbox, 400, 280)
    widget.zoom = 12
    fit({"new": ((200, 300), (600, 580))})  # A pan keeps the user's zoom.
    assert widget.zoom == 12
    fit({"new": ((200, 300), (400, 460))})  # A smaller viewport refits.
    assert widget.zoom == _geometry_zoom(item.bbox, 200, 160)


def test_geometry_takes_precedence_over_broad_bbox(map_modules):
    _, leaflet = map_modules
    item = new_item()
    item.bbox = [-180, -80, 180, 80]
    item.geometry = {"type": "Polygon", "coordinates": [[[10, 50], [11, 51], [10, 50]]]}
    _render_geometry(item)
    assert leaflet.Map.call_args.kwargs["center"] == [50.5, 10.5]
    assert leaflet.Map.call_args.kwargs["zoom"] == _geometry_zoom(
        (10, 50, 11, 51), 180, 140
    )


@pytest.mark.parametrize(
    "bounds, expected",
    [((10, 50, 11, 51), 7), ((0, 0, 0, 0), 16), ((-180, -90, 180, 90), 0)],
)
def test_geometry_zoom_handles_scene_point_and_world(bounds, expected):
    assert _geometry_zoom(bounds, 360, 280) == expected


@pytest.mark.parametrize(
    "geometry",
    [
        None,
        {"type": "Point", "coordinates": []},
        {"type": "Point", "coordinates": [1]},
    ],
)
def test_no_map_without_bounds(displayed, map_modules, geometry):
    _, leaflet = map_modules
    item = new_item()
    item.geometry = geometry

    show_assets(item)

    leaflet.Map.assert_not_called()
    assert "No assets" in displayed[0].data


@pytest.mark.parametrize("role", ["thumbnail", "overview", "visual"])
def test_preview_next_to_geometry(displayed, map_modules, monkeypatch, role):
    widgets, leaflet = map_modules
    item = new_item()
    item.bbox = [1, 2, 3, 4]
    item.add_asset("preview", Asset("preview.png", title="<Preview>", roles=[role]))
    render_preview = AsyncMock(return_value="<img src='preview'>")
    monkeypatch.setattr("cuiman.api.assets._load_preview", render_preview)

    show_assets(item, roles="data")

    render_preview.assert_awaited_once()
    assert render_preview.call_args.args == (item.assets["preview"],)
    assert "&lt;Preview&gt;" in widgets.HTML.call_args_list[0].kwargs["value"]
    assert "<img src='preview'>" in widgets.HTML.call_args_list[0].kwargs["value"]
    assert "No assets" in widgets.HTML.call_args_list[-1].kwargs["value"]
    assert widgets.HBox.call_count == 2
    assert widgets.HBox.call_args_list[0].args[0][0] is leaflet.Map.return_value
    assert widgets.HBox.call_args_list[1].args[0][1] is widgets.HBox.return_value
    assert widgets.VBox.call_args.args[0][0] is widgets.HBox.return_value
    assert widgets.VBox.call_args.args[0][1] is widgets.HTML.return_value


@pytest.mark.parametrize("with_map", [False, True])
def test_disabled_previews_prevent_asset_reads(
    displayed, map_modules, monkeypatch, with_map
):
    widgets, leaflet = map_modules
    item = new_item()
    if with_map:
        item.bbox = [1, 2, 3, 4]
    item.add_asset("preview", Asset("preview.png", roles=["thumbnail"]))
    render_preview = AsyncMock()
    monkeypatch.setattr("cuiman.api.assets._load_preview", render_preview)

    show_assets(item, previews=False)

    render_preview.assert_not_called()
    assert widgets.HBox.called is with_map
    assert leaflet.Map.called is with_map


def test_preview_without_map_and_failed_sibling(displayed, monkeypatch):
    item = new_item()
    item.add_asset("broken", Asset("broken.png", roles=["thumbnail"]))
    item.add_asset("good", Asset("good.png", roles=["overview"]))
    item.add_asset("data", Asset("data.png", roles=["data"]))
    render_preview = AsyncMock(side_effect=[None, "<img src='good'>"])
    monkeypatch.setattr("cuiman.api.assets._load_preview", render_preview)

    show_assets(item)

    assert render_preview.call_count == 2
    html = displayed[0].data
    assert "<img src='good'>" in html
    assert "<figcaption>good</figcaption>" in html
    assert "<td>broken</td>" in html
    assert html.count("<figure ") == 1


def test_failed_preview_keeps_table(displayed, monkeypatch):
    item = new_item()
    item.add_asset("preview", Asset("missing.png", roles=["thumbnail"]))
    monkeypatch.setattr("cuiman.api.assets._load_preview", AsyncMock(return_value=None))

    show_assets(item)

    assert "<td>preview</td>" in displayed[0].data
    assert "<figure " not in displayed[0].data


@pytest.mark.parametrize(
    "mime, value, expected",
    [
        ("text/html", "<p>Preview</p>", "<p>Preview</p>"),
        ("image/png", b"png", "data:image/png;base64,cG5n"),
        ("image/jpeg", "anBlZw==", "data:image/jpeg;base64,anBlZw=="),
        ("image/svg+xml", "<svg/>", "data:image/svg+xml;base64,PHN2Zy8+"),
        ("text/plain", "not renderable", None),
    ],
)
def test_render_preview_representations(monkeypatch, mime, value, expected):
    opened = object()
    formatter = MagicMock()
    formatter.format.return_value = ({mime: value}, {})
    monkeypatch.setattr("IPython.core.formatters.DisplayFormatter", lambda: formatter)

    html = _render_preview(opened)

    assert formatter.format.call_args.args == (opened,)
    if expected is None:
        assert html is None
    else:
        assert expected in html


def test_unreadable_preview(monkeypatch, tmp_path):
    asset = Asset((tmp_path / "missing.png").as_uri(), media_type="image/png")
    open_result = MagicMock(side_effect=OSError("missing"))
    assert run_sync(_load_preview, asset, open_asset=open_result) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("format_fails", [False, True])
async def test_loaded_preview_is_closed(monkeypatch, format_fails):
    opened = MagicMock()
    formatter = MagicMock()
    if format_fails:
        formatter.format.side_effect = ValueError("cannot format")
    else:
        formatter.format.return_value = ({"text/html": "<p>Preview</p>"}, {})
    monkeypatch.setattr("IPython.core.formatters.DisplayFormatter", lambda: formatter)
    asset = Asset("preview.png")
    open_asset = AsyncMock(return_value=opened)

    html = await _load_preview(asset, open_asset=open_asset)

    open_asset.assert_awaited_once_with(asset)
    opened.close.assert_called_once_with()
    assert html == (None if format_fails else "<p>Preview</p>")


@pytest.mark.parametrize("relative", [False, True])
def test_real_image_preview(displayed, tmp_path, relative):
    from PIL import Image

    image_path = tmp_path / "preview.png"
    Image.new("RGB", (2, 2), "red").save(image_path)
    item = new_item()
    item.set_self_href((tmp_path / "item.json").as_uri())
    item.add_asset(
        "preview",
        Asset(
            "preview.png" if relative else image_path.as_uri(),
            media_type="image/png",
            roles=["thumbnail"],
        ),
    )

    show_assets(item)

    html = displayed[0].data
    assert "<img src='data:image/png;base64," in html
    assert "<figcaption>preview</figcaption>" in html


@pytest.mark.parametrize("status, valid", [(200, True), (404, True), (200, False)])
def test_http_image_preview(displayed, monkeypatch, status, valid):
    from io import BytesIO

    import httpx2
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, format="PNG")
    content = buffer.getvalue() if valid else b"not an image"
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if request.url.path == "/preview.png":
            return httpx2.Response(302, headers={"location": "/image.png"})
        return httpx2.Response(status, content=content)

    client_type = httpx2.AsyncClient
    monkeypatch.setattr(
        httpx2,
        "AsyncClient",
        lambda: client_type(transport=httpx2.MockTransport(respond)),
    )
    item = new_item()
    item.add_asset(
        "preview",
        Asset(
            "https://example.invalid/preview.png",
            media_type="image/png",
            roles=["thumbnail"],
        ),
    )

    show_assets(item)

    html = displayed[0].data
    assert ("<img src='data:image/png;base64," in html) is (status == 200 and valid)
    assert "<td>preview</td>" in html
    assert requests == [
        "https://example.invalid/preview.png",
        "https://example.invalid/image.png",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("previews", [False, True])
async def test_client_preview_uses_configured_reader_on_owning_loop(
    displayed, asynchronous, previews
):
    import asyncio

    from IPython.display import HTML

    opened = []

    class PreviewOpener(JobResultOpener):
        async def accept_job_result(self, ctx):
            return isinstance(ctx.value, Asset)

        async def open_job_result(self, ctx):
            opened.append((ctx, asyncio.get_running_loop()))
            return HTML("<p>Configured preview</p>")

    class Config(ClientConfig):
        pass

    config = Config(api_url="https://process.test", auth={"auth_type": "none"})
    client = AsyncClient(config=config) if asynchronous else Client(config=config)
    unregister = client.config.register_job_result_opener(PreviewOpener)
    item = new_item()
    item.set_self_href("https://example.invalid/item.json")
    item.add_asset(
        "preview", Asset("preview.png", media_type="image/png", roles=["thumbnail"])
    )
    try:
        if asynchronous:
            await client.show_assets(item, roles="metadata", previews=previews)
        else:
            # Exercise the synchronous notebook bridge while an event loop runs.
            client.show_assets(item, roles="metadata", previews=previews)
        assert len(opened) == int(previews)
        if previews:
            ctx, loop = opened[0]
            assert ctx.config is client.config
            assert ctx.value is item.assets["preview"]
            assert ctx.location == "https://example.invalid/preview.png"
            assert ctx.output_media_type == "image/png"
            if asynchronous:
                assert loop is asyncio.get_running_loop()
        assert "No assets" in displayed[0].data
        assert ("<p>Configured preview</p>" in displayed[0].data) is previews
    finally:
        unregister()
        if asynchronous:
            await client.close()
        else:
            client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_closed_client_cannot_show_assets(displayed, asynchronous):
    client_type = AsyncClient if asynchronous else Client
    client = client_type(api_url="https://process.test", auth={"auth_type": "none"})
    if asynchronous:
        await client.close()
        with pytest.raises(RuntimeError, match="Client is closed"):
            await client.show_assets(new_item(), previews=False)
    else:
        client.close()
        with pytest.raises(RuntimeError, match="Client is closed"):
            client.show_assets(new_item(), previews=False)
    assert displayed == []
