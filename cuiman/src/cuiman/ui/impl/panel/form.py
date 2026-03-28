#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import Any

from cuiman.ui import Field, FieldFactoryRegistry, FieldMeta, FormFactory
from gavicore.models import InputDescription, Schema
from gavicore.util.undefined import Undefined

from .factories import PanelFieldGroupFactory, PanelWidgetFieldFactory


class PanelFormFactory(FormFactory):
    """
    A factory for forms whose fields use the
    [Panel](https://panel.holoviz.org/) UI library.
    """

    def __init__(self):
        super().__init__(
            FieldFactoryRegistry(
                PanelWidgetFieldFactory(),
                PanelFieldGroupFactory(),
            )
        )

    @classmethod
    def from_input_descriptions(
        cls,
        input_descriptions: dict[str, InputDescription],
        initial_value: Any | Undefined = Undefined.value,
    ) -> Field:
        return cls.from_meta(
            FieldMeta.from_input_descriptions(input_descriptions),
            initial_value=initial_value,
        )

    @classmethod
    def from_schema(
        cls,
        name: str,
        schema: Schema,
        initial_value: Any | Undefined = Undefined.value,
    ) -> Field:
        return cls.from_meta(
            FieldMeta.from_schema(name, schema), initial_value=initial_value
        )

    @classmethod
    def from_meta(
        cls,
        form_meta: FieldMeta,
        initial_value: Any | Undefined = Undefined.value,
    ) -> Field:
        factory = PanelFormFactory()
        return factory.create_form(form_meta, initial_value=initial_value)
