from typing import Any

import pytest

from cuiman.api.opener import (
    JobResultOpenContext,
    JobResultOpener,
    JobResultOpenError,
)
from cuiman.api.opener.opener import open_job_result

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


class MyAcceptRaisesOpener(JobResultOpener):
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        raise KeyError("Key not found")

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        return 137


class MyOpenRaisesOpener(JobResultOpener):
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return True

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        raise FileNotFoundError("File not found")


class MyUnableOpener(JobResultOpener):
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return False

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        return ctx.job_results


class MyUnusableOpener(JobResultOpener):
    @classmethod
    def is_usable(cls) -> bool:
        return False

    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return True

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        return 137


class MyIsUsableRaisesOpener(MyUnusableOpener):
    @classmethod
    def is_usable(cls) -> bool:
        raise AttributeError()


@pytest.mark.asyncio
async def test_open_job_result_ok():
    ctx = new_ctx(data_type=dict)
    assert await open_job_result(ctx, MyGoodOpener) == ctx.job_results.root

    ctx = new_ctx(data_type=dict, output_name="b")
    assert await open_job_result(ctx, MyGoodOpener) == 2.5


@pytest.mark.asyncio
async def test_open_job_result_ok_others_failing():
    ctx = new_ctx(data_type=dict, output_name="b")
    assert (
        await open_job_result(
            ctx, MyAcceptRaisesOpener, MyIsUsableRaisesOpener, MyGoodOpener
        )
        == 2.5
    )


@pytest.mark.asyncio
async def test_open_job_result_fails():
    ctx = new_ctx(data_type=dict)

    with pytest.raises(
        JobResultOpenError, match="Job result opener failure: File not found"
    ):
        await open_job_result(ctx, MyOpenRaisesOpener)

    with pytest.raises(
        JobResultOpenError,
        match=(
            r"Job result opener failure \(one other opener failed too\): "
            r"File not found"
        ),
    ):
        await open_job_result(ctx, MyOpenRaisesOpener, MyOpenRaisesOpener)

    with pytest.raises(
        JobResultOpenError,
        match=(
            r"Job result opener failure \(3 other openers failed too\): "
            r"File not found"
        ),
    ):
        await open_job_result(
            ctx,
            MyOpenRaisesOpener,
            MyOpenRaisesOpener,
            MyOpenRaisesOpener,
            MyOpenRaisesOpener,
        )


@pytest.mark.asyncio
async def test_open_job_result_no_opener_found():
    with pytest.raises(JobResultOpenError, match="No job result openers provided"):
        await open_job_result(new_ctx())

    with pytest.raises(
        JobResultOpenError,
        match="No job result opener found",
    ):
        await open_job_result(new_ctx(), MyUnableOpener, MyUnableOpener, MyUnableOpener)

    with pytest.raises(
        JobResultOpenError,
        match="No job result opener found",
    ):
        await open_job_result(
            new_ctx(),
            MyIsUsableRaisesOpener,
            MyIsUsableRaisesOpener,
            MyIsUsableRaisesOpener,
        )

    with pytest.raises(
        JobResultOpenError,
        match="No job result opener found",
    ):
        await open_job_result(
            new_ctx(),
            MyUnusableOpener,
            MyUnusableOpener,
            MyUnusableOpener,
        )


@pytest.mark.asyncio
async def test_open_job_result_checks_openers():
    with pytest.raises(
        TypeError, match="Type compatible with JobResultOpener expected, but got 123"
    ):
        # noinspection PyTypeChecker
        await open_job_result(
            new_ctx(),
            MyUnusableOpener,
            123,
        )
