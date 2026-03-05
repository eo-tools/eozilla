from typing import Any

import pytest

from cuiman.api.opener import (
    JobResultOpenContext,
    JobResultOpener,
    JobResultOpenerRegistry,
)
from cuiman.api.opener.registry import OpenerError

from .test_context import new_ctx


class MyGoodOpener(JobResultOpener):
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        return (
            ctx.data_type is dict
            and isinstance(ctx.job_results, dict)
            and sorted(ctx.job_results.keys()) == ["a", "b", "c"]
        )

    async def open(self, ctx: JobResultOpenContext) -> Any:
        if ctx.output_name in ["a", "b", "c"]:
            return ctx.job_results[ctx.output_name]
        else:
            return dict(ctx.job_results)


class MyFailingAcceptOpener(JobResultOpener):
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        raise KeyError("Key not found")

    async def open(self, ctx: JobResultOpenContext) -> Any:
        return 137


class MyFailingOpenOpener(JobResultOpener):
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        return True

    async def open(self, ctx: JobResultOpenContext) -> Any:
        raise FileNotFoundError("File not found")


class MyUnableOpener(JobResultOpener):
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        return False

    async def open(self, ctx: JobResultOpenContext) -> Any:
        return ctx.job_results


def test_initially_empty():
    registry = JobResultOpenerRegistry()
    assert len(registry.openers) == 0


def test_default():
    registry = JobResultOpenerRegistry.create_default()
    # Adjust here, once we've added some default openers
    assert len(registry.openers) == 0


def test_clear():
    registry = JobResultOpenerRegistry()
    registry.register(MyGoodOpener())
    assert len(registry.openers) == 1
    registry.clear()
    assert len(registry.openers) == 0


def test_register():
    registry = JobResultOpenerRegistry()
    my_opener = MyGoodOpener()

    unregister = registry.register(my_opener)

    assert callable(unregister)
    assert my_opener in registry.openers

    unregister()
    assert my_opener not in registry.openers


@pytest.mark.asyncio
async def test_open_result():
    registry = JobResultOpenerRegistry()
    registry.register(MyGoodOpener())

    ctx = new_ctx(data_type=dict)
    assert await registry.open_result(ctx) == ctx.job_results

    ctx = new_ctx(data_type=dict, output_name="b")
    assert await registry.open_result(ctx) == 2.5


@pytest.mark.asyncio
async def test_open_result_fails():
    registry = JobResultOpenerRegistry()
    registry.register(MyFailingOpenOpener())

    ctx = new_ctx(data_type=dict)

    with pytest.raises(OpenerError, match="Job result opener failure: File not found"):
        await registry.open_result(ctx)

    registry.register(MyFailingOpenOpener())

    with pytest.raises(
        OpenerError,
        match=(
            r"Job result opener failure \(one other opener failed too\): "
            r"File not found"
        ),
    ):
        await registry.open_result(ctx)

    registry.register(MyFailingOpenOpener())
    registry.register(MyFailingOpenOpener())

    with pytest.raises(
        OpenerError,
        match=(
            r"Job result opener failure \(3 other openers failed too\): "
            r"File not found"
        ),
    ):
        await registry.open_result(ctx)


@pytest.mark.asyncio
async def test_no_opener_found():
    registry = JobResultOpenerRegistry()
    with pytest.raises(OpenerError, match="No job result openers registered"):
        await registry.open_result(new_ctx())

    registry.register(MyUnableOpener())
    registry.register(MyUnableOpener())
    registry.register(MyUnableOpener())

    with pytest.raises(
        OpenerError,
        match="No job result opener found for ",
    ):
        await registry.open_result(new_ctx())


@pytest.mark.asyncio
async def test_accept_result_fails():
    registry = JobResultOpenerRegistry()
    registry.register(MyFailingAcceptOpener())
    registry.register(MyGoodOpener())
    ctx = new_ctx(data_type=dict, output_name="b")
    assert await registry.open_result(ctx) == 2.5
