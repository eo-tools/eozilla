#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.metadata import version

__version__ = version("procodile")

from gavicore.util.request import ExecutionRequest

from .artifacts import ArtifactRef, ArtifactStore, ExecutionContext
from .job import Job, JobCancelledException, JobContext
from .process import Process, additional_parameters
from .registry import ProcessRegistry
from .workflow import (
    FromMain,
    FromStep,
    Workflow,
    WorkflowRegistry,
    WorkflowStepRegistry,
)

"""Processes development API."""

__all__ = [
    "additional_parameters",
    "ArtifactRef",
    "ArtifactStore",
    "__version__",
    "ExecutionRequest",
    "ExecutionContext",
    "FromStep",
    "FromMain",
    "Job",
    "JobContext",
    "JobCancelledException",
    "ProcessRegistry",
    "Process",
    "WorkflowRegistry",
    "WorkflowStepRegistry",
    "Workflow",
]
