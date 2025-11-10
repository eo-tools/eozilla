#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import Any

import click
import pydantic

from gavicore.util.request import ExecutionRequest


def create_execution_request(
    cls,
    process_id: str | None = None,
    dotpath: bool = False,
    request_path: str | None = None,
    inputs: list[str] | None = None,
    subscribers: list[str] | None = None,
) -> ExecutionRequest:
    try:
        return ExecutionRequest.create(
            process_id=process_id,
            dotpath=dotpath,
            inputs=inputs,
            subscribers=subscribers,
            request_path=request_path,
        )
    except pydantic.ValidationError as e:
        raise click.ClickException(f"Execution request is invalid: {e}")
