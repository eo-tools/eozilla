# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

import linecache
import re
import subprocess
import sys
from datetime import datetime, timezone
from html import unescape
from types import SimpleNamespace

import pytest
from pystac import Asset, Item, ItemCollection

from cuiman.api import AsyncClient, Client
from cuiman.api import assets


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["standalone", "sync", "async"])
@pytest.mark.parametrize(
    "argument, expected",
    [
        ("named", "named"),
        ("items[0]", "items[0]"),
        ("items", "items[0]"),
        ("collection", "collection.items[0]"),
        ("items=named", "named"),
        ("identity(named)", "identity(named)"),
        ("named if True else other", "(named if True else other)"),
        ("[named] + [other]", "([named] + [other])[0]"),
        ("\n    named,\n    previews=False,\n", "named"),
    ],
)
async def test_copied_expression_uses_public_argument(
    monkeypatch, tmp_path, entry, argument, expected
):
    outputs = []
    monkeypatch.setattr("IPython.display.display", outputs.append)
    monkeypatch.setitem(sys.modules, "ipyleaflet", None)
    item = Item("example", None, None, datetime.now(timezone.utc), {})
    item.add_asset("result", Asset("missing.csv"))
    client = Client(api_url="https://process.test", auth={"auth_type": "none"})
    async_client = AsyncClient(
        api_url="https://process.test", auth={"auth_type": "none"}
    )
    scope = {
        "assets": assets,
        "client": client,
        "async_client": async_client,
        "named": item,
        "other": item,
        "items": [item],
        "collection": ItemCollection([item], clone_items=False),
        "identity": lambda value: value,
    }
    call = {
        "standalone": "await assets.display_assets",
        "sync": "client.show_assets",
        "async": "await async_client.show_assets",
    }[entry]
    source = f"async def run():\n    {call}({argument})\n"
    path = tmp_path / "caller.py"
    path.write_text(source)
    exec(compile(source, str(path), "exec"), scope)  # noqa: S102
    try:
        await scope["run"]()
        copied = unescape(
            re.search("data-copy='(.*?)' type=", outputs[0].data).group(1)
        )
        assert copied == f"{expected}.assets['result']"
        assert eval(copied, scope) is item.assets["result"]  # noqa: S307
    finally:
        client.close()
        await async_client.close()


def test_ipython_cells_aliases_same_line_and_earlier_cell_functions():
    source = """
import re
from datetime import datetime, timezone
from html import unescape
from unittest.mock import patch
from IPython.core.interactiveshell import InteractiveShell
from pystac import Asset, Item
from cuiman.api import assets
shell = InteractiveShell.instance()
item = Item("example", None, None, datetime.now(timezone.utc), {})
item.add_asset("result", Asset("missing.csv"))
shell.user_ns.update(display_assets=assets.display_assets, alias=assets.display_assets,
                     named=item, items=[item])
outputs = []
with patch("IPython.display.display", outputs.append), patch.object(assets, "_render_geometry", return_value=None):
    for cell in [
        "await display_assets(named); await display_assets(items)",
        "await alias(items=named)",
        "async def earlier():\\n    await display_assets(named)",
        "await earlier()",
    ]:
        result = shell.run_cell(cell, store_history=True)
        assert result.error_before_exec is None, result.error_before_exec
        assert result.error_in_exec is None, result.error_in_exec
copied = [unescape(re.search("data-copy='(.*?)' type=", output.data).group(1)) for output in outputs]
assert copied == ["named.assets['result']", "items[0].assets['result']",
                  "named.assets['result']", "named.assets['result']"], copied
"""
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", source], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "source, expected",
    [
        ("show_assets(named)", "named"),
        ("client.show_assets(items=named)", "named"),
        ("await show_assets(named)", "named"),
        ("functions[0](named)", None),
        ("unrelated(named)", None),
        ("show_assets(named); show_assets(other)", None),
        ("show_assets(*items)", None),
        ("show_assets(**kwargs)", None),
        ("show_assets()", None),
        ("show_assets(", None),
        ("", None),
    ],
)
def test_source_fallback_without_instruction_positions(monkeypatch, source, expected):
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_filename="<asset-source>"),
        f_globals={},
        f_lasti=0,
        f_lineno=1,
    )
    monkeypatch.setitem(
        linecache.cache,
        "<asset-source>",
        (len(source), None, [source], "<asset-source>"),
    )
    monkeypatch.setattr("dis.get_instructions", lambda *args, **kwargs: [])
    assert assets._get_call_argument_source(frame, "show_assets") == expected


def test_missing_frame_and_missing_source():
    assert assets._get_call_argument_source(None, "show_assets") is None
    frame = SimpleNamespace(
        f_code=compile("pass", "<missing-asset-source>", "exec"),
        f_globals={},
        f_lasti=0,
        f_lineno=1,
    )
    assert assets._get_call_argument_source(frame, "show_assets") is None


def test_missing_current_frame(monkeypatch):
    monkeypatch.setattr(assets, "currentframe", lambda: None)
    assert assets._get_items_expression() is None


@pytest.mark.asyncio
async def test_deferred_coroutine_uses_fallback(monkeypatch):
    # The await is no longer at the original call site; don't invent an expression.
    outputs = []
    monkeypatch.setattr("IPython.display.display", outputs.append)
    monkeypatch.setitem(sys.modules, "ipyleaflet", None)
    item = Item("example", None, None, datetime.now(timezone.utc), {})
    item.add_asset("result", Asset("missing.csv"))
    coroutine = assets.display_assets(item)

    await coroutine

    assert "data-copy='item.assets[" in outputs[0].data
