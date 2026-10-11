# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

import re
import sys
from datetime import date
from html import unescape
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import AnyUrl

from cuiman.api import AsyncClient, Client
from cuiman.api.assets import display_assets
from cuiman.api.assets.job_results import _render_job_results
from gavicore.models.core import JobResults, Link, QualifiedValue


@pytest.mark.parametrize("root", [None, {}])
def test_empty_results(root):
    html = _render_job_results(JobResults(root=root)).data
    assert "No outputs" in html
    assert "Job results" in html
    assert "<table>" not in html


def test_mixed_results_are_escaped_and_keep_null_and_scalars():
    results = JobResults(
        root={
            "<output>": {"text": "<script>", "items": [1, False]},
            "count": 0,
            "enabled": False,
            "optional": None,
            "text": "<b>hello</b>",
            "report": Link(href="https://example.test/report.csv", type="text/csv"),
            "qualified": QualifiedValue(value=[1, 2], mediaType="application/json"),
            "untyped": Link(href="javascript:alert(1)"),
            "plain": QualifiedValue(value="hello"),
        }
    )
    html = _render_job_results(results, expression="results[0]").data
    assert "<th>Output</th><th>Kind</th><th>Media type</th>" in html
    assert "&lt;output&gt;" in html and "&lt;script&gt;" in html
    assert "&lt;b&gt;hello&lt;/b&gt;" in html
    assert "<details><summary>JSON</summary>" in html
    assert "<td>0</td>" in html and "<td>false</td>" in html
    assert "<td>null</td>" in html
    assert "<td>text/csv</td>" in html and "<td>application/json</td>" in html
    assert "href='https://example.test/report.csv'" in html
    assert "href='javascript:" not in html
    expressions = re.findall("data-copy='(.*?)' type=", html)
    assert [unescape(value) for value in expressions] == [
        f"results[0].root[{key!r}]" for key in results.root
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["sync", "async", "standalone"])
@pytest.mark.parametrize("previews", [True, False])
async def test_job_results_display_without_pystac_or_output_reads(
    monkeypatch, entry, previews
):
    outputs = []
    monkeypatch.setattr("IPython.display.display", outputs.append)
    monkeypatch.setitem(sys.modules, "pystac", None)
    results = JobResults(root={"report": Link(href="https://example.test/report")})
    mock_type = MagicMock if entry == "sync" else AsyncMock
    opener = mock_type()
    if entry == "standalone":
        await display_assets(results, open_asset=opener, previews=previews, roles=[])
    else:
        client_type = Client if entry == "sync" else AsyncClient
        client = client_type(api_url="https://example.test", auth={"auth_type": "none"})
        monkeypatch.setattr(client, "open_job_result", opener)
        try:
            if entry == "sync":
                client.show_assets(results, previews=previews, roles=[])
            else:
                await client.show_assets(results, previews=previews, roles=[])
        finally:
            if entry == "sync":
                client.close()
            else:
                await client.close()
    opener.assert_not_called()
    assert len(outputs) == 1
    html = outputs[0].data
    assert "<td>report</td>" in html
    assert "results.root['report']" in unescape(html)


def test_missing_caller_source_uses_results_placeholder():
    html = _render_job_results(JobResults(root={"value": 42})).data
    assert "results.root['value']" in unescape(html)


def test_python_values_use_model_json_serialization():
    results = JobResults(
        root={
            "date": date(2026, 10, 11),
            "url": AnyUrl("https://example.test"),
            "bytes": b"hello",
            "qualified": QualifiedValue(value={"date": date(2026, 10, 11)}),
        }
    )
    html = unescape(_render_job_results(results).data)
    assert '"2026-10-11"' in html
    assert '"https://example.test/"' in html
    assert '"hello"' in html
