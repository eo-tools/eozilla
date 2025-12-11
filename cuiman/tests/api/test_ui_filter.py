#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated, Any, Literal

from pydantic import Field

from cuiman.api.config import ClientConfig
from gavicore.models import InputDescription, ProcessDescription
from gavicore.util.model import extend_model


def test_ui_input_filtering():
    # Add an application-specific configuration knows how to evaluate the new field.
    class InputDescriptionX(InputDescription):
        level: Annotated[
            Literal["common", "advanced"],
            Field(
                alias="x-uiLevel",
                title="UI level",
                description="Describes the level of this input.",
            ),
        ] = "common"

    extend_model(InputDescription, InputDescriptionX)

    # An application-specific configuration knows how to evaluate the new field.
    class AnolisClientConfig(ClientConfig):
        @classmethod
        def accept_input(
            cls,
            process_description: ProcessDescription,
            input_name: str,
            input_description: InputDescription,
            **params: Any,
        ):
            input_level = input_description.level or "common"
            requested_level = params.pop("level") or "common"
            return input_level == "common" or input_level == requested_level

    # level = "common" (the default)
    com_input = InputDescription(**{"schema": {"type": "number"}})
    # level = "advanced"
    adv_input = InputDescription(
        **{"schema": {"type": "number"}, "x-uiLevel": "advanced"}
    )

    process = ProcessDescription(
        id="p",
        version="0",
        inputs={
            "com_input": com_input,
            "adv_input": adv_input,
        },
    )

    config = AnolisClientConfig()
    assert config.accept_input(process, "com_input", com_input, level="common") is True
    assert (
        config.accept_input(process, "com_input", com_input, level="advanced") is True
    )
    assert config.accept_input(process, "adv_input", adv_input, level="common") is False
    assert (
        config.accept_input(process, "adv_input", adv_input, level="advanced") is True
    )
