from typing import Any

import pytest

from cuiman.api.opener import OpenerRegistry, OpenerContext, Opener
from cuiman.api.opener.registry import OpenerError

from .test_context import new_ctx


def test_initially_empty():
    registry = OpenerRegistry()
    assert len(registry.openers) == 0


def test_default():
    registry = OpenerRegistry.create_default()
    # Adjust here, once we've added some default openers
    assert len(registry.openers) == 0


def test_register():
    registry = OpenerRegistry()
    my_opener = MyOpener()

    unregister = registry.register(my_opener)

    assert callable(unregister)
    assert my_opener in registry.openers

    unregister()
    assert my_opener not in registry.openers


@pytest.mark.asyncio
async def test_open_result():
    registry = OpenerRegistry()
    registry.register(MyOpener())

    ctx = new_ctx(data_type=dict)
    assert await registry.open_result(ctx) == ctx.job_results

    ctx = new_ctx(data_type=dict, output_name="b")
    assert await registry.open_result(ctx) == 2.5


@pytest.mark.asyncio
async def test_open_result_fails():
    registry = OpenerRegistry()
    registry.register(MyFailingOpener())

    ctx = new_ctx(data_type=dict)

    with pytest.raises(OpenerError, match="Job result opener failure: File not found"):
        await registry.open_result(ctx)

    registry.register(MyFailingOpener())

    with pytest.raises(
        OpenerError,
        match=(
            r"Job result opener failure \(one other opener failed too\): "
            r"File not found"
        ),
    ):
        await registry.open_result(ctx)

    registry.register(MyFailingOpener())
    registry.register(MyFailingOpener())

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
    registry = OpenerRegistry()
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


class MyOpener(Opener):
    async def accept(self, ctx: OpenerContext) -> bool:
        return (
            ctx.data_type is dict
            and isinstance(ctx.job_results, dict)
            and sorted(ctx.job_results.keys()) == ["a", "b", "c"]
        )

    async def open(self, ctx: OpenerContext) -> Any:
        if ctx.output_name in ["a", "b", "c"]:
            return ctx.job_results[ctx.output_name]
        else:
            return dict(ctx.job_results)


class MyFailingOpener(Opener):
    async def accept(self, ctx: OpenerContext) -> bool:
        return True

    async def open(self, ctx: OpenerContext) -> Any:
        raise FileNotFoundError("File not found")


class MyUnableOpener(Opener):
    async def accept(self, ctx: OpenerContext) -> bool:
        return False

    async def open(self, ctx: OpenerContext) -> Any:
        return ctx.job_results
