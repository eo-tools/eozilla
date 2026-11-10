#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import warnings
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import replace
from inspect import isclass
from typing import Any, ClassVar

from cuiman.api.exceptions import ClientWarning

from .context import JobResultReadContext, _copy_options
from .errors import JobResultReadError, StacJobResultReadError


class JobResultReader(ABC):
    """Abstract base class for pluggable job result readers.

    A reader handles the authoritative selected value and effective location
    in the [context object][cuiman.api.reader.JobResultReadContext] `ctx` passed to
    [accept_job_result()][cuiman.api.reader.JobResultReader.accept_job_result]
    and [read_job_result()][cuiman.api.reader.JobResultReader.read_job_result].
    Original job results and process metadata are optional source facts; they
    must not be used to select a sibling output. If `data_type` is provided, a
    reader MUST be able to return that type,
    otherwise [accept_job_result()][cuiman.api.reader.JobResultReader.accept_job_result]
    should return `False`.

    Dispatch also validates the returned value with ``isinstance``. An
    incompatible result is closed when possible and treated as a reader failure.

    Output selection is validated before dispatch, so acceptance does not need
    to resolve output names or distinguish missing outputs from selected nulls.
    """

    reader_id: ClassVar[str] = ""
    """Stable identity, explicitly declared by every registered concrete reader."""

    option_policy: ClassVar[str | None] = None
    """Inheritable backend option policy, independent of reader identity."""

    @classmethod
    def is_usable(cls) -> bool:
        """Check whether this reader is usable in the
        current OS or Python environment.
        """
        return True

    @classmethod
    def _unavailable_error(cls, ctx: JobResultReadContext) -> Exception | None:
        return None

    @abstractmethod
    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        """Check if this reader can potentially be used to read
        the given job result.

        More specifically, the method is used to exclude this reader
        from the list of potential readers for the given job results.

        For performance reasons, an implementation should focus on
        determining the unability to read the job results and early
        return `False` in this case.

        The method is not expected to raise any errors.

        Args:
            ctx: The job result read context used to check.

        Returns:
            `True` if this reader can read the job results, `False` otherwise.
        """

    @abstractmethod
    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        """Read the result of a job.

        The method is expected to raise an appropriate error
        if it is not possible to read the job results.

        Args:
            ctx: The job result read context used to read.

        Returns:
            The value from reading the job result.
        """


async def read_job_result(
    ctx: JobResultReadContext, *reader_types: type[JobResultReader]
) -> Any:
    """
    Read a job result.

    The method iterates given `readers` in the order provided
    to find any reader that accepts the given `ctx`, and if so,
    will read it without raising.

    Args:
        ctx: The context used by the readers to check whether
            an output can be read and, if so, to read it.
        reader_types: The list of reader types to use.

    Returns:
        The value from reading a job result.

    Raises:
        JobResultReadError: If no reader was found or all suitable
            readers raised while reading.
    """
    if ctx.data_type is not None and not isinstance(ctx.data_type, type):
        raise JobResultReadError("data_type must be a Python type")
    if ctx.reader_id is not None:
        reader_types = tuple(t for t in reader_types if t.reader_id == ctx.reader_id)
        if not reader_types:
            raise JobResultReadError(f"Unknown job result reader: {ctx.reader_id!r}")
    # Use first matching reader, otherwise try next
    errors: list[tuple[type[JobResultReader], Exception]] = []
    accepted_reader_count: int = 0
    for reader_type in reader_types:
        assert_reader_type_valid(reader_type)
        candidate_ctx = replace(
            ctx,
            options=_copy_options(ctx.options),
            resolved_options={},
            option_sources={},
        )

        reader: JobResultReader | None = None
        try:
            if reader_type.is_usable():
                reader = reader_type()
            else:
                unavailable = reader_type._unavailable_error(candidate_ctx)
                if unavailable is not None:
                    errors.append((reader_type, unavailable))
                    accepted_reader_count += 1
        except Exception as e:
            _warn(reader_type, _safe_error(ctx, e))

        if (
            errors
            and isinstance(errors[-1][1], StacJobResultReadError)
            and errors[-1][1].required
        ):
            break

        if reader is not None:
            accepted: bool
            try:
                accepted = await reader.accept_job_result(candidate_ctx)
                accepted_reader_count += int(accepted)
            except Exception as e:
                _warn(type(reader), _safe_error(ctx, e))
                accepted = False

            if accepted:
                try:
                    from cuiman.api.assets import as_stac_asset

                    if (
                        reader.option_policy
                        and as_stac_asset(candidate_ctx.value) is not None
                    ):
                        from .impl._stac.options import prepare_asset_reader

                        candidate_ctx = await prepare_asset_reader(
                            candidate_ctx,
                            reader.reader_id,
                            option_policy=reader.option_policy,
                        )
                    result = await reader.read_job_result(candidate_ctx)
                    if ctx.data_type is not None and not isinstance(
                        result, ctx.data_type
                    ):
                        try:
                            close = getattr(result, "close", None)
                            if callable(close):
                                close()
                        finally:
                            raise JobResultReadError(
                                f"Reader returned {type(result).__name__}; "
                                f"expected {ctx.data_type.__name__}"
                            )
                    ctx.resolved_options = deepcopy(candidate_ctx.resolved_options)
                    ctx.option_sources = dict(candidate_ctx.option_sources)
                    return result
                except Exception as e:
                    ctx.resolved_options = deepcopy(candidate_ctx.resolved_options)
                    ctx.option_sources = dict(candidate_ctx.option_sources)
                    e = _safe_error(ctx, e)
                    errors.append((reader_type, e))
                    if isinstance(e, StacJobResultReadError) and e.required:
                        break

    # Error management
    if not errors:
        if not reader_types:
            raise JobResultReadError("No job result readers provided")
        else:
            raise JobResultReadError("No job result reader found")
    error_messages = "\n".join(f"* {t.__name__}: {e}" for t, e in errors)
    raise JobResultReadError(
        f"Job result reader failure:\n{error_messages}"
    ) from ExceptionGroup(
        f"{len(errors)} of {accepted_reader_count} possible reader"
        f"{'' if accepted_reader_count == 1 else 's'} failed",
        [e for _, e in errors],
    )


def _warn(reader_type: type[JobResultReader], error: Exception):
    warnings.warn(
        "Unexpected error occurred in "
        f"{reader_type.__name__}: {type(error).__name__}: {error}",
        category=ClientWarning,
        stacklevel=2,
    )


def _safe_error(ctx: JobResultReadContext, error: Exception) -> Exception:
    from cuiman.api.assets import as_stac_asset

    if as_stac_asset(ctx.value) is not None:
        return JobResultReadError(f"Asset reading failed ({type(error).__name__})")
    return error


def assert_reader_type_valid(reader_type: type[JobResultReader]):
    """Raise TypeError unless the value is a job result reader class."""
    if not isclass(reader_type) or not issubclass(reader_type, JobResultReader):
        raise TypeError(
            f"Type compatible with {JobResultReader.__name__} expected, "
            f"but got {reader_type}"
        )
