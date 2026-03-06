from typing import Any

import pytest

from cuiman.api.opener import (
    JobResultOpenContext,
    JobResultOpener,
    JobResultOpenError,
)
from cuiman.api.opener.opener import open_job_result
from gavicore.models import InlineOrRefValue, InlineValue

from .test_context import new_ctx


class MyGoodOpener(JobResultOpener):
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return (
            ctx.data_type is dict
            and isinstance(ctx.job_results.root, dict)
            and sorted(ctx.job_results.root.keys()) == ["a", "b", "c"]
        )

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        results_root = ctx.job_results.root
        if ctx.output_name in ["a", "b", "c"]:
            if results_root is not None:
                return results_root.get(ctx.output_name)
        return results_root


class MyFailingAcceptOpener(JobResultOpener):
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        raise KeyError("Key not found")

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        return 137


class MyFailingOpenOpener(JobResultOpener):
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return True

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        raise FileNotFoundError("File not found")


class MyUnableOpener(JobResultOpener):
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return False

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        return ctx.job_results


@pytest.mark.asyncio
async def test_open_job_result_ok():
    ctx = new_ctx(data_type=dict)
    assert await open_job_result(ctx, MyGoodOpener()) == ctx.job_results.root

    ctx = new_ctx(data_type=dict, output_name="b")
    assert await open_job_result(ctx, MyGoodOpener()) == InlineOrRefValue(
        InlineValue(2.5)
    )


@pytest.mark.asyncio
async def test_open_job_result_fails():
    ctx = new_ctx(data_type=dict)

    with pytest.raises(
        JobResultOpenError, match="Job result opener failure: File not found"
    ):
        await open_job_result(ctx, MyFailingOpenOpener())

    with pytest.raises(
        JobResultOpenError,
        match=(
            r"Job result opener failure \(one other opener failed too\): "
            r"File not found"
        ),
    ):
        await open_job_result(ctx, MyFailingOpenOpener(), MyFailingOpenOpener())

    with pytest.raises(
        JobResultOpenError,
        match=(
            r"Job result opener failure \(3 other openers failed too\): "
            r"File not found"
        ),
    ):
        await open_job_result(
            ctx,
            MyFailingOpenOpener(),
            MyFailingOpenOpener(),
            MyFailingOpenOpener(),
            MyFailingOpenOpener(),
        )


@pytest.mark.asyncio
async def test_open_job_result_no_opener_found():
    with pytest.raises(JobResultOpenError, match="No job result openers provided"):
        await open_job_result(new_ctx())

    with pytest.raises(
        JobResultOpenError,
        match="No job result opener found",
    ):
        await open_job_result(
            new_ctx(), MyUnableOpener(), MyUnableOpener(), MyUnableOpener()
        )


@pytest.mark.asyncio
async def test_open_job_result_accept_result_fails():
    ctx = new_ctx(data_type=dict, output_name="b")
    assert await open_job_result(
        ctx, MyFailingAcceptOpener(), MyGoodOpener()
    ) == InlineOrRefValue(InlineValue(2.5))
