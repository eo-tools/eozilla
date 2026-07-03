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


class MyOpensEverythingOpener(JobResultOpener):
    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return True

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        return 137


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


class MyOpenRaisesOpener1(MyOpenRaisesOpener):
    pass


class MyOpenRaisesOpener2(MyOpenRaisesOpener):
    pass


class MyOpenRaisesOpener3(MyOpenRaisesOpener):
    pass


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

    assert (
        await open_job_result(
            ctx,
            MyOpensEverythingOpener,
            MyOpenRaisesOpener1,
            MyOpenRaisesOpener2,
            MyOpenRaisesOpener3,
        )
        == 137
    )

    assert (
        await open_job_result(
            ctx,
            MyOpenRaisesOpener1,
            MyOpenRaisesOpener2,
            MyOpenRaisesOpener3,
            MyOpensEverythingOpener,
        )
        == 137
    )


@pytest.mark.asyncio
async def test_open_job_result_fails():
    ctx = new_ctx(data_type=dict)

    with pytest.raises(
        JobResultOpenError,
        match=r"Job result opener failure:\n\* MyOpenRaisesOpener: File not found",
    ):
        await open_job_result(ctx, MyOpenRaisesOpener)

    with pytest.raises(
        JobResultOpenError,
        match=(
            r"Job result opener failure:\n"
            r"\* MyOpenRaisesOpener1: File not found\n"
            r"\* MyOpenRaisesOpener2: File not found\n"
            r"\* MyOpenRaisesOpener3: File not found"
        ),
    ):
        await open_job_result(
            ctx, MyOpenRaisesOpener1, MyOpenRaisesOpener2, MyOpenRaisesOpener3
        )


@pytest.mark.asyncio
async def test_open_job_result_counts_accepted_openers_only():
    ctx = new_ctx(data_type=dict)

    with pytest.raises(JobResultOpenError) as exc_info:
        await open_job_result(ctx, MyUnableOpener, MyOpenRaisesOpener)

    cause = exc_info.value.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert str(cause) == "1 of 1 possible opener failed (1 sub-exception)"


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
