#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import warnings
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import replace
from inspect import isclass
from typing import Any

from cuiman.api.exceptions import ClientWarning
from .context import JobResultOpenContext, _copy_options
from .errors import JobResultOpenError, StacJobResultOpenError


class JobResultOpener(ABC):
    """Abstract base class for pluggable job result openers.

    An opener handles the authoritative selected value and effective location
    in the [context object][cuiman.api.opener.JobResultOpenContext] `ctx` passed to
    [accept_job_result()][cuiman.api.opener.JobResultOpener.accept_job_result]
    and [open_job_result()][cuiman.api.opener.JobResultOpener.open_job_result].
    Original job results and process metadata are optional source facts; they
    must not be used to select a sibling output. If `data_type` is provided, an
    opener MUST be able to return that type,
    otherwise [accept_job_result()][cuiman.api.opener.JobResultOpener.accept_job_result]
    should return `False`.

    Output selection is validated before dispatch, so acceptance does not need
    to resolve output names or distinguish missing outputs from selected nulls.
    """

    @classmethod
    def is_usable(cls) -> bool:
        """Check whether this opener is usable in the
        current OS or Python environment.
        """
        return True

    @classmethod
    def _unavailable_error(cls, ctx: JobResultOpenContext) -> Exception | None:
        return None

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
        opener_types: The list of opener types to use.

    Returns:
        The value from opening a job result.

    Raises:
        JobResultOpenError: If no opener was found or all suitable
            openers raised while opening.
    """
    # Use first matching opener, otherwise try next
    errors: list[tuple[type[JobResultOpener], Exception]] = []
    accepted_opener_count: int = 0
    for opener_type in opener_types:
        assert_opener_type_valid(opener_type)
        candidate_ctx = replace(
            ctx,
            options=_copy_options(ctx.options),
            resolved_options={},
            option_sources={},
        )

        opener: JobResultOpener | None = None
        try:
            if opener_type.is_usable():
                opener = opener_type()
            else:
                unavailable = opener_type._unavailable_error(candidate_ctx)
                if unavailable is not None:
                    errors.append((opener_type, unavailable))
                    accepted_opener_count += 1
        except Exception as e:
            _warn(opener_type, _safe_error(ctx, e))

        if (
            errors
            and isinstance(errors[-1][1], StacJobResultOpenError)
            and errors[-1][1].required
        ):
            break

        if opener is not None:
            accepted: bool
            try:
                accepted = await opener.accept_job_result(candidate_ctx)
                accepted_opener_count += int(accepted)
            except Exception as e:
                _warn(type(opener), _safe_error(ctx, e))
                accepted = False

            if accepted:
                try:
                    result = await opener.open_job_result(candidate_ctx)
                    ctx.resolved_options = deepcopy(candidate_ctx.resolved_options)
                    ctx.option_sources = dict(candidate_ctx.option_sources)
                    return result
                except Exception as e:
                    ctx.resolved_options = deepcopy(candidate_ctx.resolved_options)
                    ctx.option_sources = dict(candidate_ctx.option_sources)
                    e = _safe_error(ctx, e)
                    errors.append((opener_type, e))
                    if isinstance(e, StacJobResultOpenError) and e.required:
                        break

    # Error management
    if not errors:
        if not opener_types:
            raise JobResultOpenError("No job result openers provided")
        else:
            raise JobResultOpenError("No job result opener found")
    error_messages = "\n".join(f"* {t.__name__}: {e}" for t, e in errors)
    raise JobResultOpenError(
        f"Job result opener failure:\n{error_messages}"
    ) from ExceptionGroup(
        f"{len(errors)} of {accepted_opener_count} possible opener"
        f"{'' if accepted_opener_count == 1 else 's'} failed",
        [e for _, e in errors],
    )


def _warn(opener_type: type[JobResultOpener], error: Exception):
    warnings.warn(
        "Unexpected error occurred in "
        f"{opener_type.__name__}: {type(error).__name__}: {error}",
        category=ClientWarning,
        stacklevel=2,
    )


def _safe_error(ctx: JobResultOpenContext, error: Exception) -> Exception:
    from cuiman.api.assets import as_stac_asset

    if as_stac_asset(ctx.value) is not None:
        return JobResultOpenError(f"Asset opening failed ({type(error).__name__})")
    return error


def assert_opener_type_valid(opener_type: type[JobResultOpener]):
    if not isclass(opener_type) or not issubclass(opener_type, JobResultOpener):
        raise TypeError(
            f"Type compatible with {JobResultOpener.__name__} expected, "
            f"but got {opener_type}"
        )
