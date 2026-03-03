#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from collections.abc import Awaitable
from typing import Callable

from .opener import Opener, OpenerContext

import asyncio
import concurrent.futures
from typing import Any


class OpenerError(RuntimeError):
    pass


class OpenerRegistry:
    @classmethod
    def create_default(cls):
        return OpenerRegistry()

    def __init__(self, *openers: Opener):
        self._openers = list(openers)

    def register(self, opener: Opener) -> Callable[[], None]:
        """Register a job results opener.

        Args:
            opener: the opener
        Returns:
            A function that can be called to unregister the opener.
        """

        def unregister():
            self._openers.remove(opener)

        self._openers.append(opener)
        return unregister

    async def open_result(self, ctx: OpenerContext) -> Any:
        """
        Open a job result.

        All actual logic lives here.
        """
        openers = list(self._openers)
        if not openers:
            raise OpenerError("No job result openers registered")

        errors = []
        for opener in openers:
            if await opener.accept(ctx):
                try:
                    return await opener.open_result(ctx)
                except Exception as e:
                    errors.append(e)

        if errors:
            first_error = errors[0]
            num_other_openers = len(errors) - 1
            msg_detail = ""
            if num_other_openers == 1:
                msg_detail = " (one other opener failed too)"
            elif num_other_openers > 1:
                msg_detail = f" ({num_other_openers} other openers failed too)"

            raise OpenerError(
                f"Job result opener failure{msg_detail}: {first_error}"
            ) from first_error
        else:
            raise OpenerError(f"No job result opener found for {ctx.job_results}")

    def open_result_sync(self, ctx: OpenerContext) -> Any:
        """
        Synchronous wrapper around the asynchronous `open_result()` method.

        Why this exists:
        - Allows use in plain scripts without `await`
        - Allows use in Jupyter notebooks
        - Avoids duplicating business logic

        Strategy:
        1. If NO event loop is running → safe to use asyncio.run().
        2. If an event loop IS already running (e.g., Jupyter),
           we must NOT block it or nest loops.
           Instead, we run the coroutine in a separate thread,
           which creates and owns its own fresh event loop.
        """

        try:
            # This raises RuntimeError if no loop is running
            asyncio.get_running_loop()
        except RuntimeError:
            # No event loop active in this thread.
            # Safe and simplest path.
            return asyncio.run(self.open_result(ctx))

        # If we reach here, we're inside an already running event loop.
        # Example: Jupyter notebook.
        #
        # Calling asyncio.run() directly would raise:
        #   RuntimeError: asyncio.run() cannot be called from a running event loop
        #
        # Therefore, we offload execution to a new thread.
        # That thread will:
        #   - create its own event loop
        #   - run the coroutine
        #   - return the result synchronously

        def runner():
            # This runs in a separate thread.
            # asyncio.run() is safe here because
            # this thread has no running loop.
            return asyncio.run(self.open_result(ctx))

        # Use a single-worker ThreadPoolExecutor.
        # We keep it short-lived and deterministic.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(runner)
            return future.result()  # Re-raises exceptions correctly
