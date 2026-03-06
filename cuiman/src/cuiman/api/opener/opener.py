#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import warnings
from abc import ABC, abstractmethod
from inspect import isclass
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
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        """Check if this opener can potentially be used to open
        the given job result.

        More specifically, the method is used to exclude this opener
        from the list of potential openers for the given job results.

        For performance reasons, an implementation should focus on
        determining the unability to open the job results and early
        return `False` in this case.

        The method is not expected to raise any errors.

        Args:
            ctx: The job result open context used to check.

        Returns:
            `True` if this opener can open the job results, `False` otherwise.
        """

    @abstractmethod
    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        """Open the result of a job.

        The method is expected to raise an appropriate error
        if it is not possible to open the job results.

        Args:
            ctx: The job result open context used to open.

        Returns:
            The value from opening the job result.
        """


async def open_job_result(
    ctx: JobResultOpenContext, *opener_types: type[JobResultOpener]
) -> Any:
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
    for opener_type in opener_types:
        assert_opener_type_valid(opener_type)

        opener: JobResultOpener | None = None
        try:
            if opener_type.is_usable():
                opener = opener_type()
        except Exception as e:
            _warn(opener_type, e)

        if opener is not None:
            try:
                accepted = await opener.accept_job_result(ctx)
            except Exception as e:
                _warn(type(opener), e)
                accepted = False

            if accepted:
                try:
                    return await opener.open_job_result(ctx)
                except Exception as e:
                    errors.append(e)

    # Error management
    if not errors:
        if not opener_types:
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


def _warn(opener_type: type[JobResultOpener], error: Exception):
    warnings.warn(
        "Unexpected error occurred in "
        f"{opener_type.__name__}: {type(error).__name__}: {error}",
        UserWarning,
        stacklevel=2,
    )


def assert_opener_type_valid(opener_type: type[JobResultOpener]):
    if not isclass(opener_type):
        raise TypeError(
            f"Type compatible with {JobResultOpener.__name__} expected, "
            f"but got {opener_type}"
        )
