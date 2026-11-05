from typing import Any

import pytest

from cuiman.api.reader import (
    JobResultReadContext,
    JobResultReader,
    JobResultReadError,
)
from cuiman.api.reader.reader import read_job_result

from .test_context import new_ctx


class MyGoodReader(JobResultReader):
    reader_id = "MyGoodReader"

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        return ctx.data_type in (str, float, bool) and isinstance(ctx.value, ctx.data_type)

    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        return ctx.value


class MyOpensEverythingReader(JobResultReader):
    reader_id = "MyOpensEverythingReader"

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        return True

    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        return 137


class MyAcceptRaisesReader(JobResultReader):
    reader_id = "MyAcceptRaisesReader"

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        raise KeyError("Key not found")

    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        return 137


class MyOpenRaisesReader(JobResultReader):
    reader_id = "MyOpenRaisesReader"

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        return True

    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        raise FileNotFoundError("File not found")


class MyOpenRaisesReader1(MyOpenRaisesReader):
    reader_id = "MyOpenRaisesReader1"

    pass


class MyOpenRaisesReader2(MyOpenRaisesReader):
    reader_id = "MyOpenRaisesReader2"

    pass


class MyOpenRaisesReader3(MyOpenRaisesReader):
    reader_id = "MyOpenRaisesReader3"

    pass


class MyUnableReader(JobResultReader):
    reader_id = "MyUnableReader"

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        return False

    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        return ctx.job_results


class MyUnusableReader(JobResultReader):
    reader_id = "MyUnusableReader"

    @classmethod
    def is_usable(cls) -> bool:
        return False

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        return True

    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        return 137


class MyIsUsableRaisesReader(MyUnusableReader):
    reader_id = "MyIsUsableRaisesReader"

    @classmethod
    def is_usable(cls) -> bool:
        raise AttributeError()


@pytest.mark.asyncio
async def test_read_job_result_ok():
    ctx = new_ctx(data_type=str)
    assert await read_job_result(ctx, MyGoodReader) == "out.nc"

    ctx = new_ctx(data_type=float, output_name="b")
    assert await read_job_result(ctx, MyGoodReader) == 2.5


@pytest.mark.asyncio
async def test_read_job_result_ok_others_failing():
    ctx = new_ctx(data_type=float, output_name="b")
    assert (
        await read_job_result(
            ctx, MyAcceptRaisesReader, MyIsUsableRaisesReader, MyGoodReader
        )
        == 2.5
    )

    ctx.data_type = int
    assert (
        await read_job_result(
            ctx,
            MyOpensEverythingReader,
            MyOpenRaisesReader1,
            MyOpenRaisesReader2,
            MyOpenRaisesReader3,
        )
        == 137
    )

    assert (
        await read_job_result(
            ctx,
            MyOpenRaisesReader1,
            MyOpenRaisesReader2,
            MyOpenRaisesReader3,
            MyOpensEverythingReader,
        )
        == 137
    )


@pytest.mark.asyncio
async def test_read_job_result_fails():
    ctx = new_ctx(data_type=dict)

    with pytest.raises(
        JobResultReadError,
        match=r"Job result reader failure:\n\* MyOpenRaisesReader: File not found",
    ):
        await read_job_result(ctx, MyOpenRaisesReader)

    with pytest.raises(
        JobResultReadError,
        match=(
            r"Job result reader failure:\n"
            r"\* MyOpenRaisesReader1: File not found\n"
            r"\* MyOpenRaisesReader2: File not found\n"
            r"\* MyOpenRaisesReader3: File not found"
        ),
    ):
        await read_job_result(
            ctx, MyOpenRaisesReader1, MyOpenRaisesReader2, MyOpenRaisesReader3
        )


@pytest.mark.asyncio
async def test_read_job_result_counts_accepted_readers_only():
    ctx = new_ctx(data_type=dict)

    with pytest.raises(JobResultReadError) as exc_info:
        await read_job_result(ctx, MyUnableReader, MyOpenRaisesReader)

    cause = exc_info.value.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert str(cause) == "1 of 1 possible reader failed (1 sub-exception)"


@pytest.mark.asyncio
async def test_read_job_result_no_reader_found():
    with pytest.raises(JobResultReadError, match="No job result readers provided"):
        await read_job_result(new_ctx())

    with pytest.raises(
        JobResultReadError,
        match="No job result reader found",
    ):
        await read_job_result(new_ctx(), MyUnableReader, MyUnableReader, MyUnableReader)

    with pytest.raises(
        JobResultReadError,
        match="No job result reader found",
    ):
        await read_job_result(
            new_ctx(),
            MyIsUsableRaisesReader,
            MyIsUsableRaisesReader,
            MyIsUsableRaisesReader,
        )

    with pytest.raises(
        JobResultReadError,
        match="No job result reader found",
    ):
        await read_job_result(
            new_ctx(),
            MyUnusableReader,
            MyUnusableReader,
            MyUnusableReader,
        )


@pytest.mark.asyncio
async def test_read_job_result_checks_readers():
    with pytest.raises(
        TypeError, match="Type compatible with JobResultReader expected, but got 123"
    ):
        # noinspection PyTypeChecker
        await read_job_result(
            new_ctx(),
            MyUnusableReader,
            123,
        )
