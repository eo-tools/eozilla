#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any

from .context import JobResultOpenContext


class JobResultOpener(ABC):
    """Abstract base class for pluggable job result openers.

    An opener implementation is free to use the information
    in the [context object](OpenerContext) `ctx` passed to the
    methods [accept()][accept] and [open()][open].
    However, if `data_type` or `output_name` are provided, an
    opener MUST be able to deal with them, otherwise [accept()][accept]
    should return `False`.
    """

    @abstractmethod
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        """Checks if this opener can open the given job results.

        The method is not expected to raise any errors.

        Args:
            ctx: The job results open context used to check.

        Returns:
            `True` if this opener can open the job results, `False` otherwise.
        """

    @abstractmethod
    async def open(self, ctx: JobResultOpenContext) -> Any:
        """Open the results of a job.

        The method is expected to raise an appropriate error
        if it is not possible to open the job results.

        Args:
            ctx: The job results open context used to open.

        Returns:
            The value from opening the job result.
        """
