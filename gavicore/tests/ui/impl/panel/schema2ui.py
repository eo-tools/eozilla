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
from gavicore.ui import FieldMeta
from gavicore.ui.impl.panel import PanelField
from gavicore.ui.vm import ViewModelChangeEvent

pn.extension()

schemas_dir = Path(__file__).parent / "schemas"

app = typer.Typer()
app_name = "schema2ui"


@app.command(name=app_name)
def main(
    schema_spec: Annotated[
        str,
        typer.Option(help="Path to the schema YAML file or a known schema name."),
    ] = "",
) -> None:
    """Convert a selected schema into a Panel UI."""

    schemas = load_schemas(schema_spec)
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
        form_field = PanelField.from_meta(field_meta)
        form_field.view_model.watch(_on_view_model_change)
        ui_column[1] = form_field.view
        _change_current_value(form_field.view_model.value)

    def _on_selection_change(event):
        _change_selected_schema(event.new)

    select.param.watch(_on_selection_change, "value")
    _change_selected_schema(selected_schema_name)

    pn.serve(panel, title=f"{app_name}")


def load_schemas(schema_spec: str | None = None) -> list[tuple[Path, Schema]]:
    schemas: list[tuple[Path, Schema]]
    if schema_spec:
        schema_path: Path = Path(schema_spec)
        if len(schema_path.parts) == 1 and schema_path.suffix == "":
            schema_path = schemas_dir / f"{schema_spec}.yaml"
        schemas = [(schema_path, load_schema(schema_path))]
    else:
        schemas = [
            (schema_path, load_schema(schema_path))
            for schema_path in schemas_dir.iterdir()
        ]
    return schemas


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
