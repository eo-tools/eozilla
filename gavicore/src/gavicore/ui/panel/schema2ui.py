#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
from pathlib import Path
from typing import Annotated, Any

import panel as pn
import typer
import yaml

from gavicore.models import Schema
from gavicore.ui import FieldMeta, FieldFactoryRegistry
from gavicore.ui.panel import PanelField
from gavicore.ui.vm import ViewModelChangeEvent

pn.extension()

GAVICORE_ROOT = (Path(__file__).parent / ".." / ".." / ".." / "..").resolve()
DEFAULT_SCHEMAS_DIR = GAVICORE_ROOT / "tests" / "ui" / "schemas"

APP_NAME = "schema2ui"

app = typer.Typer()


@app.command(name=APP_NAME)
def main(
    schema_path: Annotated[
        str,
        typer.Argument(
            help="Path to the schema YAML file or a known schema name.",
        ),
    ] = DEFAULT_SCHEMAS_DIR,
) -> None:
    """Convert a selected schema into a Panel UI."""
    schemas_to_ui(schema_path)


def schemas_to_ui(
    *schema_paths: str,
    registry: FieldFactoryRegistry["PanelField"] | None = None,
) -> None:
    """Convert a selected schema into a Panel UI."""

    schemas = load_schemas(*schema_paths)
    schema_dict = {p.stem.title(): s for p, s in schemas}
    schema_names = list(schema_dict.keys())

    selected_schema_name = schema_names[0]

    select = pn.widgets.Select(
        options=schema_names, value=selected_schema_name, size=16
    )
    text_area = pn.widgets.TextAreaInput(value="", cols=12, rows=16)

    schema_column = pn.Column(
        "## OpenAPI Schema:",
        select,
    )
    value_column = pn.Column(
        "## JSON-Value:",
        text_area,
    )
    ui_column = pn.Column(
        "## Generated UI:",
        "<placeholder>",
    )
    panel = pn.Row(pn.Column(schema_column, value_column), ui_column)

    def _on_view_model_change(event: ViewModelChangeEvent) -> None:
        _change_current_value(event.source.value)

    def _change_current_value(value: Any) -> None:
        json_text = json.dumps(value, indent=2, sort_keys=False)
        text_area.value = json_text

    def _change_selected_schema(schema_name: str):
        nonlocal selected_schema_name
        selected_schema_name = schema_name
        schema = schema_dict[selected_schema_name]
        schema.title = schema.title or ""  # Force no title if not explicitly set
        field_meta = FieldMeta.from_schema("root", schema)
        form_field = PanelField.from_meta(field_meta, field_factory_registry=registry)
        form_field.view_model.watch(_on_view_model_change)
        ui_column[1] = form_field.view
        _change_current_value(form_field.view_model.value)

    def _on_selection_change(event):
        _change_selected_schema(event.new)

    select.param.watch(_on_selection_change, "value")
    _change_selected_schema(selected_schema_name)

    pn.serve(panel, title=f"{APP_NAME}")


def load_schemas(*schema_paths: str) -> list[tuple[Path, Schema]]:
    resolved_paths: list[Path] = []
    for path in schema_paths:
        schema_path = Path(path)
        if schema_path.is_file():
            resolved_paths.append(schema_path)
        elif schema_path.is_dir():
            resolved_paths.extend(
                [
                    schema_path / p
                    for p in schema_path.iterdir()
                    if p.suffix.lower() in (".yaml", ".yml", ".json")
                ]
            )
    return [(p, load_schema(p)) for p in resolved_paths]


def load_schema(path: Path) -> Schema:
    suffix = path.suffix.lower()
    with open(path) as f:
        if suffix in (".yaml", ".yml"):
            schema_dict = yaml.safe_load(f)
        else:
            schema_dict = json.load(f)
    return Schema(**schema_dict)


if __name__ == "__main__":
    app()
