#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.metadata import version


__version__ = version("procodile")

from procodile.src.procodile.cli.cli import get_cli
from procodile.src.procodile.job import Job, JobCancelledException, JobContext
from procodile.src.procodile.process import Process
from procodile.src.procodile.registry import ProcessRegistry
from s2gos_common.util.request import ExecutionRequest

"""Processes development API."""

__all__ = [
    "__version__",
    "ExecutionRequest",
    "Job",
    "JobContext",
    "JobCancelledException",
    "ProcessRegistry",
    "Process",
    "get_cli",
]
