#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import asyncio
import threading

import pytest

import gavicore.util.runsync as m


async def _async_return(value):
    return value


async def _async_raise(exc: Exception):
    raise exc


def test_run_sync_without_running_loop_returns_value():
    """
    This test runs in normal sync pytest context (no running event loop in this thread).
    It should take the 'asyncio.run(...)' branch.
    """
    assert m.run_sync(_async_return, 123) == 123


@pytest.mark.asyncio
async def test_run_sync_with_running_loop_uses_background_thread_and_reuses_it():
    """
    This test runs under pytest's event loop, so asyncio.get_running_loop() succeeds.
    run_sync() must NOT use asyncio.run() in this thread; it should use the background
    runner thread.

    We also check that subsequent calls reuse the same runner thread/loop (fast path).
    """
    # First call should lazily start the runner thread
    r1 = m.run_sync(_async_return, "ok")
    assert r1 == "ok"

    loop1 = m._runner_loop
    thread1 = m._runner_thread

    assert loop1 is not None
    assert thread1 is not None
    assert isinstance(loop1, asyncio.AbstractEventLoop)
    assert isinstance(thread1, threading.Thread)
    assert thread1.is_alive()

    # Second call should reuse the same thread/loop
    r2 = m.run_sync(_async_return, "again")
    assert r2 == "again"

    assert m._runner_loop is loop1
    assert m._runner_thread is thread1


def test_run_sync_propagates_exceptions_without_running_loop():
    """
    Exception propagation for the 'no running loop' branch (asyncio.run path).
    """
    with pytest.raises(ValueError) as e:
        m.run_sync(_async_raise, ValueError("boom"))
    assert str(e.value) == "boom"


@pytest.mark.asyncio
async def test_run_sync_propagates_exceptions_with_running_loop():
    """
    Exception propagation for the 'running loop' branch (background thread path).
    """
    with pytest.raises(RuntimeError) as e:
        m.run_sync(_async_raise, RuntimeError("kaboom"))
    assert str(e.value) == "kaboom"


@pytest.mark.asyncio
async def test_runner_cleanup_and_restart_covers_post_run_forever_block():
    """
    This test forces the background runner loop to STOP so that the code after
    loop.run_forever() executes (cleanup: cancel pending tasks, gather, loop.close()).

    Then it calls run_sync() again and verifies the runner is re-created.
    """
    # Ensure runner exists
    _ = m.run_sync(_async_return, 1)
    loop = m._runner_loop
    thread = m._runner_thread
    assert loop is not None
    assert thread is not None
    assert thread.is_alive()

    # Create a pending task on the runner loop so the cleanup branch
    # has something to cancel.
    async def create_pending_task():
        # This task will remain pending unless canceled.
        asyncio.create_task(asyncio.sleep(10))
        return "created"

    # Submit to the runner loop directly (not via run_sync) so we can
    # be precise about creating a pending task there.
    fut = asyncio.run_coroutine_threadsafe(create_pending_task(), loop)
    assert fut.result(timeout=5) == "created"

    # Now STOP the runner loop so loop.run_forever() returns and cleanup runs.
    loop.call_soon_threadsafe(loop.stop)

    # The runner thread should exit quickly after stop; join to ensure cleanup executed.
    thread.join(timeout=5)
    assert not thread.is_alive()

    # At this point, the old globals may still point to a closed loop/thread.
    # A new call from within a running loop must recreate them.
    r = m.run_sync(_async_return, 99)
    assert r == 99

    new_loop = m._runner_loop
    new_thread = m._runner_thread
    assert new_loop is not None
    assert new_thread is not None
    assert new_thread.is_alive()
    assert new_thread is not thread  # restarted


@pytest.mark.asyncio
async def test_run_sync_is_safe_to_call_repeatedly_quickly():
    """
    Minor stress check: repeated quick calls while a loop is running.
    This also helps cover timing-sensitive lines and ensures no deadlocks.
    """
    for i in range(20):
        assert m.run_sync(_async_return, i) == i
