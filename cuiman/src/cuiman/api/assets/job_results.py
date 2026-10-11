# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Notebook tables for raw job outputs, without fetching linked resources."""

from html import escape
from json import dumps
from typing import Any

from gavicore.models.core import JobResults, Link, QualifiedValue

from .common import _copy_button, _render_link, _styles


def _render_value(value: Any) -> str:
    """Render JSON scalars directly and structured values as expandable JSON."""
    if isinstance(value, (dict, list)):
        return (
            "<details><summary>JSON</summary>"
            "<pre style='max-height:320px;overflow:auto;white-space:pre-wrap'>"
            f"{escape(dumps(value, ensure_ascii=False, indent=2))}</pre></details>"
        )
    return escape(dumps(value, ensure_ascii=False))


def _render_job_results(results: JobResults, *, expression: str | None = None):
    """Build an output table with safe links and copyable root access expressions."""
    from IPython.display import HTML

    rows = []
    json_values = results.model_dump(mode="json", by_alias=True) or {}
    for name, result in (results.root or {}).items():
        media_type = ""
        if isinstance(result, Link):
            kind = "Link"
            media_type = result.type or ""
            value_html = _render_link(result.href)
        elif isinstance(result, QualifiedValue):
            kind = "Inline"
            media_type = result.mediaType or ""
            value_html = _render_value(json_values[name]["value"])
        else:
            kind = "Inline"
            value_html = _render_value(json_values[name])
        access = f"{expression or 'results'}.root[{name!r}]"
        rows.append(
            "<tr>"
            f"<td>{escape(name)}</td><td>{kind}</td>"
            f"<td>{escape(media_type)}</td><td>{value_html}</td>"
            f"<td>{_copy_button(access)}</td></tr>"
        )
    table = (
        "<div class='cuiman-assets-table'><table>"
        "<thead><tr><th>Output</th><th>Kind</th><th>Media type</th>"
        "<th>Value / location</th><th>Code</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        if rows
        else "<p class='cuiman-assets-empty'><em>No outputs</em></p>"
    )
    return HTML(
        _styles() + "<section class='cuiman-assets cuiman-assets-card' "
        "style='border:1px solid #8884;overflow:hidden;margin:12px 0 24px'>"
        "<header style='padding:16px 20px 8px'><strong>Job results</strong></header>"
        f"{table}</section>"
    )
