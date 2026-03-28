#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import panel as pn
import typer
import yaml

from cuiman.ui import FieldMeta
from cuiman.ui.impl.panel import PanelFormFactory
from cuiman.ui.vm import ViewModelChangeEvent
from gavicore.models import Schema

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

    form_factory = PanelFormFactory()
    schemas = _load_schemas(schema_spec)
    schema_names = list(n for n, _s in schemas)
    schema_dict = dict(schemas)

    selected_schema_name = schema_names[0]

    select = pn.widgets.Select(
        name="Schema:",
        options=schema_names,
        value=selected_schema_name,
    )
    panel = pn.Column(
        select,
        "## Generated UI:",
        "<placeholder>",
    )

    def _change_selected_schema(schema_name):
        nonlocal selected_schema_name
        selected_schema_name = schema_name
        schema = schema_dict[selected_schema_name]
        field_meta = FieldMeta.from_schema("root", schema)
        form_field = form_factory.create_form(field_meta)
        form_field.view_model.watch(_on_view_model_change)
        _show_current_view_model_value(form_field.view_model.value)
        panel[2] = form_field.view

    def _on_selection_change(event):
        _change_selected_schema(event.new)

    select.param.watch(_on_selection_change, "value")
    _change_selected_schema(selected_schema_name)

    pn.serve(panel, title=f"{app_name}")


def _load_schemas(schema_spec: str) -> list[tuple[str, Schema]]:
    schemas: list[tuple[str, Schema]]
    if schema_spec:
        schema_path: Path = Path(schema_spec)
        if len(schema_path.parts) == 1 and schema_path.suffix == "":
            schema_path = schemas_dir / f"{schema_spec}.yaml"
        schemas = [_load_schema(schema_path)]
    else:
        schemas = [_load_schema(schema_path) for schema_path in schemas_dir.iterdir()]
    return schemas


def _load_schema(path: Path) -> tuple[str, Schema]:
    suffix = path.suffix.lower()
    with open(path) as f:
        if suffix in (".yaml", ".yml"):
            schema_dict = yaml.safe_load(f)
        else:
            schema_dict = json.load(f)
    return path.stem.title(), Schema(**schema_dict)


def _on_view_model_change(event: ViewModelChangeEvent) -> None:
    _show_current_view_model_value(event.source.value)


def _show_current_view_model_value(value: Any) -> None:
    print(80 * "-")
    print(yaml.safe_dump(value, sort_keys=False), end="")
    sys.stdout.flush()


if __name__ == "__main__":
    app()
