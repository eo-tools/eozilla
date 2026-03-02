#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from cuiman import ClientConfig
from gavicore.models import JobResults


@dataclass
class OpenerContext:
    """Context object passed to the methods of [Opener][Opener]."""

    job_results: JobResults
    options: dict[str, Any]
    config: ClientConfig


class Opener(ABC):
    """Abstract base class for pluggable openers."""

    @abstractmethod
    def accept(self, ctx: OpenerContext):
        """Return True if this opener can open the job results."""

    @abstractmethod
    def open_result(self, ctx: OpenerContext) -> Any:
        """Open the results of a job."""
