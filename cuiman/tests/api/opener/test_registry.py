from typing import Any

import pytest

from cuiman.api.opener import (
    JobResultOpenContext,
    JobResultOpener,
    JobResultOpenerRegistry,
    JobResultOpenError,
)
from gavicore.models import InlineOrRefValue, InlineValue

from .test_context import new_ctx


class MyGoodOpener(JobResultOpener):
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        return (
            ctx.data_type is dict
            and isinstance(ctx.job_results.root, dict)
            and sorted(ctx.job_results.root.keys()) == ["a", "b", "c"]
        )

    async def open(self, ctx: JobResultOpenContext) -> Any:
        results_root = ctx.job_results.root
        if ctx.output_name in ["a", "b", "c"]:
            if results_root is not None:
                return results_root.get(ctx.output_name)
        return results_root


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
    my_opener_1 = MyGoodOpener()
    my_opener_2 = MyGoodOpener()

    unregister_1 = registry.register(my_opener_1)
    unregister_2 = registry.register(my_opener_2)

    assert callable(unregister_1)
    assert callable(unregister_2)
    assert unregister_1 is not unregister_2

    assert my_opener_1 in registry.openers
    assert my_opener_2 in registry.openers

    unregister_1()

    assert my_opener_1 not in registry.openers
    assert my_opener_2 in registry.openers

    unregister_2()

    assert my_opener_1 not in registry.openers
    assert my_opener_2 not in registry.openers

    # should not harm
    unregister_1()
    unregister_2()


@pytest.mark.asyncio
async def test_open_job_result_ok():
    registry = JobResultOpenerRegistry()
    registry.register(MyGoodOpener())

    ctx = new_ctx(data_type=dict)
    assert await registry.open_job_result(ctx) == ctx.job_results.root

    ctx = new_ctx(data_type=dict, output_name="b")
    assert await registry.open_job_result(ctx) == InlineOrRefValue(InlineValue(2.5))


@pytest.mark.asyncio
async def test_open_job_result_fails():
    registry = JobResultOpenerRegistry()
    registry.register(MyFailingOpenOpener())

    ctx = new_ctx(data_type=dict)

    with pytest.raises(
        JobResultOpenError, match="Job result opener failure: File not found"
    ):
        await registry.open_job_result(ctx)

    registry.register(MyFailingOpenOpener())

    with pytest.raises(
        JobResultOpenError,
        match=(
            r"Job result opener failure \(one other opener failed too\): "
            r"File not found"
        ),
    ):
        await registry.open_job_result(ctx)

    registry.register(MyFailingOpenOpener())
    registry.register(MyFailingOpenOpener())

    with pytest.raises(
        JobResultOpenError,
        match=(
            r"Job result opener failure \(3 other openers failed too\): "
            r"File not found"
        ),
    ):
        await registry.open_job_result(ctx)


@pytest.mark.asyncio
async def test_open_job_result_no_opener_found():
    registry = JobResultOpenerRegistry()
    with pytest.raises(JobResultOpenError, match="No job result openers registered"):
        await registry.open_job_result(new_ctx())

    registry.register(MyUnableOpener())
    registry.register(MyUnableOpener())
    registry.register(MyUnableOpener())

    with pytest.raises(
        JobResultOpenError,
        match="No job result opener found for ",
    ):
        await registry.open_job_result(new_ctx())


@pytest.mark.asyncio
async def test_open_job_result_accept_result_fails():
    registry = JobResultOpenerRegistry()
    registry.register(MyGoodOpener())
    registry.register(MyFailingAcceptOpener())
    ctx = new_ctx(data_type=dict, output_name="b")
    assert await registry.open_job_result(ctx) == InlineOrRefValue(InlineValue(2.5))
