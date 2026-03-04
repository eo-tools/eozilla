#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any

from .context import OpenerContext


class Opener(ABC):
    """Abstract base class for pluggable job result openers.

    An opener implementation is free to use the information
    in the [context object](OpenerContext) `ctx` passed to the
    methods [accept()][accept] and [open()][open].
    However, if `data_type` or `output_name` are provided an
    opener MUST be able to deal with them, otherwise [accept()][accept]
    should return `False`.
    """

    @abstractmethod
    async def accept(self, ctx: OpenerContext) -> bool:
        """Return True if this opener can open the job results."""

    @abstractmethod
    async def open(self, ctx: OpenerContext) -> Any:
        """Open the results of a job."""
