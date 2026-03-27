#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

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
app_name = "panel-form-tester"


@app.command(name=app_name)
def main(
    schema_spec: Annotated[
        str, typer.Argument(help="Path to the schema YAML file or a known schema name.")
    ],
) -> None:
    schema_path = Path(schema_spec)
    if len(schema_path.parts) == 1 and schema_path.suffix == "":
        schema_path = schemas_dir / f"{schema_spec}.yaml"

    schema = _load_schema(schema_path)
    field_meta = FieldMeta.from_schema("root", schema)
    form_factory = PanelFormFactory()

    # --- create the form ---
    form_field = form_factory.create_form(field_meta)

    # --- observe value changes ---
    form_field.view_model.watch(_on_value_change)

    # print initial value
    _show_current_value(form_field.view_model.value)

    # --- show UI ---
    pn.serve(form_field.view, title=f"{app_name} - {schema_spec}")


def _load_schema(path) -> Schema:
    with open(path) as f:
        schema_dict = yaml.safe_load(f)
    return Schema(**schema_dict)


def _on_value_change(event: ViewModelChangeEvent) -> None:
    _show_current_value(event.source.value)


def _show_current_value(value: Any) -> None:
    print(80 * "-")
    print(yaml.safe_dump(value, sort_keys=False), end="")
    sys.stdout.flush()


if __name__ == "__main__":
    app()
