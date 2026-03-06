from typing import Any

from cuiman.api.opener import (
    JobResultOpenContext,
    JobResultOpener,
    JobResultOpenerRegistry,
)


class DummyOpener(JobResultOpener):
    async def accept(self, _ctx: JobResultOpenContext) -> bool:
        return False

    async def open(self, _ctx: JobResultOpenContext) -> Any:
        return None


def test_initially_empty():
    registry = JobResultOpenerRegistry()
    assert len(registry.openers) == 0


def test_default():
    registry = JobResultOpenerRegistry.create_default()
    # Adjust here, once we've added some default openers
    assert len(registry.openers) == 3


def test_clear():
    registry = JobResultOpenerRegistry()
    registry.register(DummyOpener())
    assert len(registry.openers) == 1
    registry.clear()
    assert len(registry.openers) == 0


def test_register():
    registry = JobResultOpenerRegistry()
    my_opener_1 = DummyOpener()
    my_opener_2 = DummyOpener()

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
