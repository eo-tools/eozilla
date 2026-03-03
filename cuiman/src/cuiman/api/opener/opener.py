#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any

from cuiman import ClientConfig
from gavicore.models import JobResults, ProcessDescription


@dataclass
class OpenerContext:
    """Context object passed to the methods of [Opener][Opener]."""

    config: ClientConfig
    """Configuration of the client."""

    job_id: str
    """ID of the job."""

    process_description: ProcessDescription
    """Description of the process that produced the results."""

    job_results: JobResults
    """Results of a job."""

    output_name: str | None
    """Name of the output that should be opened."""

    data_type: type | None
    """Data type of the output that should be opened."""

    options: dict[str, Any]
    """Data type of the output that should be opened."""


class Opener(ABC):
    """Abstract base class for pluggable openers."""

    @abstractmethod
    async def accept(self, ctx: OpenerContext) -> Awaitable[bool]:
        """Return True if this opener can open the job results."""

    @abstractmethod
    async def open_result(self, ctx: OpenerContext) -> Awaitable[Any]:
        """Open the results of a job."""
