#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")

# ---------------------------------------------------------------------------
# Thread + event-loop runner infrastructure
# ---------------------------------------------------------------------------
#
# Goal:
#   Provide a synchronous wrapper for async functions that works in BOTH cases:
#     1) No event loop is running in the current thread  -> we can use asyncio.run()
#     2) An event loop *is* running (e.g. Jupyter)        -> we must NOT nest loops
#
# In case (2), we run the coroutine in a *dedicated background thread* that
# owns its own event loop. We keep that thread alive and reuse it for every call,
# so we don't pay the overhead of spinning up a new ThreadPoolExecutor per call.
#
# Design:
#   - Start one daemon thread lazily on first use.
#   - Inside that thread: run an asyncio event loop forever.
#   - To execute a coroutine from sync code:
#       * create the coroutine in the caller thread
#       * submit it to the background loop using asyncio.run_coroutine_threadsafe
#       * block on concurrent.futures.Future.result() to get the value/exception


def run_sync(
    async_fn: Callable[P, Awaitable[T]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """
    Run an async function from synchronous code and return its result.

    Works in:
      - normal scripts (no running event loop)  -> uses asyncio.run()
      - Jupyter notebooks (running event loop)  -> submits work to background loop thread

    Important notes:
      - If called from a thread with NO running loop, we prefer asyncio.run()
        because it's the simplest and most deterministic.
      - If called while a loop is running (common in Jupyter), we MUST NOT call:
          * asyncio.run()          (raises RuntimeError)
          * loop.run_until_complete() on the same loop (already running)
        Instead, we use a dedicated background event loop thread and submit
        the coroutine there.
      - Exceptions raised inside the async function are re-raised here unchanged.
    """
    try:
        # If this succeeds, we are in a context with a running event loop
        # (e.g. Jupyter cell, or inside some async application).
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this thread -> safe to create a temporary loop and run.
        return asyncio.run(async_fn(*args, **kwargs))

    # Running loop detected. Use the reusable background loop thread.
    loop = _ensure_runner_thread()

    # Create the coroutine object in the caller thread.
    # This is fine: the coroutine will actually execute in the background loop.
    coro = async_fn(*args, **kwargs)

    # Submit coroutine to the background event loop thread.
    # Returns a concurrent.futures.Future.
    future = asyncio.run_coroutine_threadsafe(coro, loop)

    # Block synchronously until done.
    # If the coroutine raises, .result() re-raises the same exception here.
    return future.result()


_runner_lock = threading.Lock()
_runner_loop: asyncio.AbstractEventLoop | None = None
_runner_thread: threading.Thread | None = None


def _ensure_runner_thread() -> asyncio.AbstractEventLoop:
    """
    Ensure a dedicated background thread with a running event loop exists.

    Returns the event loop that lives in that thread.
    """
    global _runner_loop, _runner_thread

    # Fast path: already initialized
    if (
        _runner_loop is not None
        and _runner_thread is not None
        and _runner_thread.is_alive()
    ):
        return _runner_loop

    # Slow path: initialize once, safely, even if multiple threads call run_sync() at once
    with _runner_lock:
        if (
            _runner_loop is not None
            and _runner_thread is not None
            and _runner_thread.is_alive()
        ):
            return _runner_loop

        loop_ready = threading.Event()

        def thread_main():
            """
            Target function for the background thread.

            - Create a fresh event loop *in this thread*
            - Store it globally
            - Run it forever so we can submit coroutines to it later
            """
            global _runner_loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            _runner_loop = loop
            loop_ready.set()

            # Keep the loop running, ready to accept submitted coroutines.
            loop.run_forever()

            # If the loop is ever stopped, clean up pending tasks (defensive).
            # (In normal use we never stop it; it's a daemon thread.)
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()

        # Daemon thread: it won't prevent process exit.
        _runner_thread = threading.Thread(
            target=thread_main, name="async-runner", daemon=True
        )
        _runner_thread.start()

        # Wait until the loop is created and stored
        loop_ready.wait()
        assert _runner_loop is not None
        return _runner_loop
