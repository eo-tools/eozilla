#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gavicore.models import JobResults, ProcessDescription


if TYPE_CHECKING:
    from cuiman.api.config import ClientConfig


@dataclass
class OpenerContext:
    """Context object passed to the methods of [Opener][Opener]."""

    config: "ClientConfig"
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
    async def accept(self, ctx: OpenerContext) -> bool:
        """Return True if this opener can open the job results."""

    @abstractmethod
    async def open(self, ctx: OpenerContext) -> Any:
        """Open the results of a job."""
