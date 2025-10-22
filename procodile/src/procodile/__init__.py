#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.metadata import version


__version__ = version("procodile")

from s2gos_common.util.request import ExecutionRequest
from .job import Job, JobCancelledException, JobContext
from .process import Process
from .registry import ProcessRegistry

"""Processes development API."""

__all__ = [
    "__version__",
    "ExecutionRequest",
    "Job",
    "JobContext",
    "JobCancelledException",
    "ProcessRegistry",
    "Process",
]
