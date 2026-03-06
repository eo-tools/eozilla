#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import warnings
from abc import ABC, abstractmethod
from typing import Any

from .context import JobResultOpenContext
from .errors import JobResultOpenError


class JobResultOpener(ABC):
    """Abstract base class for pluggable job result openers.

    An opener implementation is free to use the information
    in the [context object](JobResultOpenContext) `ctx` passed to the
    methods [accept()][accept] and [open()][open].
    However, if `data_type` or `output_name` are provided, an
    opener MUST be able to deal with them, otherwise [accept()][accept]
    should return `False`.
    """

    @classmethod
    def is_usable(cls) -> bool:
        """Check whether this opener is usable in the
        current OS or Python environment.
        """
        return True

    @abstractmethod
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        """Checks if this opener can open the given job results.

        The method is not expected to raise any errors.

        Args:
            ctx: The job result open context used to check.

        Returns:
            `True` if this opener can open the job results, `False` otherwise.
        """

    @abstractmethod
    async def open(self, ctx: JobResultOpenContext) -> Any:
        """Open the results of a job.

        The method is expected to raise an appropriate error
        if it is not possible to open the job results.

        Args:
            ctx: The job result open context used to open.

        Returns:
            The value from opening the job result.
        """


async def open_job_result(ctx: JobResultOpenContext, *openers: JobResultOpener) -> Any:
    """
    Open a job result.

    The method iterates given `openers` in the order provided
    to find any opener that accepts the given `ctx`, and if so,
    will open it without raising.

    Args:
        ctx: The context used by the openers to check whether
            an output can be opened and, if so, to open it.
        openers: The list of openers to use.

    Returns:
        The value from opening a job result.

    Raises:
        JobResultOpenError: If no opener was found or all suitable
            openers raised while opening.
    """
    # Use first matching opener, otherwise try next
    errors: list[Exception] = []
    for opener in openers:
        # noinspection PyBroadException
        try:
            accepted = await opener.accept(ctx)
        except Exception as e:
            warnings.warn(
                (
                    f"Exception caught in opener {type(opener).__name__}.accept(), "
                    f"please fix: {e}"
                ),
                stacklevel=2,
            )
            accepted = False

        if accepted:
            try:
                return await opener.open(ctx)
            except Exception as e:
                errors.append(e)

    # Error management
    if not errors:
        if not openers:
            raise JobResultOpenError("No job result openers provided")
        else:
            raise JobResultOpenError("No job result opener found")
    first_error = errors[0]
    num_other_openers = len(errors) - 1
    msg_detail = ""
    if num_other_openers == 1:
        msg_detail = " (one other opener failed too)"
    elif num_other_openers > 1:
        msg_detail = f" ({num_other_openers} other openers failed too)"
    raise JobResultOpenError(
        f"Job result opener failure{msg_detail}: {first_error}"
    ) from first_error
