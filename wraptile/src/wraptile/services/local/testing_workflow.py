#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import time
from pathlib import Path
from typing import Annotated, Optional

import pydantic
from pydantic import Field

from gavicore.models import InputDescription, Link, Schema
from procodile import FromMain, JobContext, WorkflowRegistry, additional_parameters
from wraptile.services.local import LocalService

workflow_registry = WorkflowRegistry()

service = LocalService(
    title="Eozilla API Server (local dummy for testing)",
    description="Local test server implementing the OGC API - Processes 1.0 Standard",
    process_registry=workflow_registry,
)

registry = service.process_registry
first_workflow = registry.get_or_create_workflow(id="first_workflow")


@first_workflow.main(
    id="first_step",
    # inputs={
    #     "id": Field(title="main input")
    # },
    outputs={
        "a": Field(title="main result", description="The result of the main step"),
        "id_for_fifth": Field(
            title="input for fifth step", description="input for fifth step"
        ),
    },
    description=(
        "This workflow currently just tests the execution orchestration of steps "
        "defined in it."
    ),
)
def fun_a(
    id: Annotated[str, Field(title="main input")] = "hithere",
    id2: Annotated[str, Field(title="inbput for fifth step")] = "watchadoing",
) -> tuple[str, str]:
    print("ran from main:::", id, id2)
    return id, id2


@first_workflow.step(
    id="second_step",
    inputs={"id": FromMain(output="a")},
    outputs={
        "final": Field(title="Final output"),
    },
)
def fun_b(id: str) -> str:
    print("ran from second_step:::", id * 2)
    return id * 2
