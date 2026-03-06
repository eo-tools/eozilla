from typing import Any

from cuiman.api.opener import (
    JobResultOpenContext,
    JobResultOpener,
    JobResultOpenerRegistry,
)


class DummyOpener1(JobResultOpener):
    async def accept_job_result(self, _ctx: JobResultOpenContext) -> bool:
        return False

    async def open_job_result(self, _ctx: JobResultOpenContext) -> Any:
        return None


class DummyOpener2(DummyOpener1):
    pass


class DummyOpener3(DummyOpener1):
    pass


def test_initially_empty():
    registry = JobResultOpenerRegistry()
    assert len(registry.opener_types) == 0


def test_default():
    registry = JobResultOpenerRegistry.create_default()
    # Adjust here, once we've added some default openers
    assert len(registry.opener_types) == 0


def test_register():
    registry = JobResultOpenerRegistry()
    assert len(registry.opener_types) == 0

    registry.register(DummyOpener1)
    assert len(registry.opener_types) == 1
    registry.register(DummyOpener2)
    assert len(registry.opener_types) == 2
    registry.register(DummyOpener3)
    assert len(registry.opener_types) == 3
    assert registry.opener_types == (DummyOpener3, DummyOpener2, DummyOpener1)

    registry.register(DummyOpener1)
    assert len(registry.opener_types) == 3
    assert registry.opener_types == (DummyOpener1, DummyOpener3, DummyOpener2)


def test_register_unregister():
    registry = JobResultOpenerRegistry()
    unregister_1 = registry.register(DummyOpener1)
    unregister_2 = registry.register(DummyOpener2)
    assert callable(unregister_1)
    assert callable(unregister_2)
    assert unregister_1 is not unregister_2
    assert DummyOpener1 in registry.opener_types
    assert DummyOpener2 in registry.opener_types

    unregister_1()
    assert DummyOpener1 not in registry.opener_types
    assert DummyOpener2 in registry.opener_types

    unregister_2()
    assert DummyOpener1 not in registry.opener_types
    assert DummyOpener2 not in registry.opener_types

    # should not harm
    unregister_1()
    unregister_2()


def test_clear():
    registry = JobResultOpenerRegistry()
    registry.register(DummyOpener1)
    registry.register(DummyOpener2)
    registry.register(DummyOpener3)
    assert len(registry.opener_types) == 3
    registry.clear()
    assert len(registry.opener_types) == 0
