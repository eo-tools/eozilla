#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Shared notebook styles, links, copy buttons, and caller expressions."""

from html import escape
from inspect import currentframe
from types import FrameType
from urllib.parse import unquote, urlsplit


def _styles() -> str:
    """Return the shared asset table and card styles."""
    return (
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
        # Outrank notebook HTML table rules in both plain HTML and widget outputs.
        ".cuiman-assets .cuiman-assets-table table{width:100%;border-collapse:collapse;"
        "text-align:left;background:transparent}"
        ".cuiman-assets .cuiman-assets-table table th{font-size:11px;text-transform:uppercase;"
        "letter-spacing:.06em;opacity:.6;font-weight:600;text-align:left}"
        ".cuiman-assets .cuiman-assets-table table td,"
        ".cuiman-assets .cuiman-assets-table table th{padding:10px 12px;"
        "border-bottom:1px solid #8882;text-align:left}"
        ".cuiman-assets .cuiman-assets-table table td:first-child{font-weight:600}"
        ".cuiman-assets .cuiman-assets-table table td:last-child,"
        ".cuiman-assets .cuiman-assets-table table th:last-child{width:32px;text-align:center}"
        ".cuiman-assets .cuiman-assets-table table tbody tr:last-child td{border-bottom:0}"
        ".cuiman-assets .cuiman-assets-table table tbody tr:nth-child(odd){background:#8881}"
        ".cuiman-assets .cuiman-assets-table table tbody tr:nth-child(even){background:transparent}"
        ".cuiman-assets .cuiman-assets-table table tbody tr:hover{background:#8882}"
        ".cuiman-assets a{color:#3b9fa5;text-decoration:none}"
        ".cuiman-assets a:hover{text-decoration:underline}"
        ".cuiman-assets-empty{padding:0 20px}"
        ".cuiman-assets-previews figure{margin:0;width:160px;min-width:0}"
        ".cuiman-assets-previews img{display:block;width:100%;"
        "height:140px;object-fit:contain;background:#8881;border-radius:8px}"
        ".cuiman-assets-previews figcaption{font:12px/1.5 system-ui,sans-serif;"
        "opacity:.65;padding:8px 2px}"
        "</style>"
    )


def _render_link(href: str) -> str:
    """Render a file link, escaping labels and rejecting active URL schemes."""
    path = urlsplit(href.replace("\\", "/")).path.rstrip("/")
    filename = unquote(path.rsplit("/", 1)[-1]) or href
    scheme = urlsplit(href).scheme.lower()

    if scheme in ("", "http", "https", "file"):
        return (
            f"<a href='{escape(href, quote=True)}' "
            "style='overflow-wrap:anywhere'>"
            f"{escape(filename)}</a>"
        )
    else:
        return escape(filename)


def _copy_button(expression: str) -> str:
    """Render a button that copies an escaped Python access expression."""
    return (
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
