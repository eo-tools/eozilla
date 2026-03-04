#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable

from .opener import Opener, OpenerContext

from typing import Any


class OpenerError(RuntimeError):
    pass


class OpenerRegistry:
    @classmethod
    def create_default(cls):
        return OpenerRegistry()

    def __init__(self, *openers: Opener):
        self._openers = list(openers)

    def clear(self) -> None:
        self._openers = []

    @property
    def openers(self) -> tuple[Opener, ...]:
        return tuple(self._openers)

    def register(self, opener: Opener) -> Callable[[], None]:
        """Register a job results opener.

        Args:
            opener: The opener.

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
        return await open_result(ctx, *self._openers)


async def open_result(ctx: OpenerContext, *openers: Opener) -> Any:
    """
    Open a job result.

    All actual logic lives here.
    """
    if not openers:
        raise OpenerError("No job result openers registered")

    # Use first matching opener, otherwise try next
    errors: list[Exception] = []
    for opener in openers:
        # noinspection PyBroadException
        try:
            accepted = await opener.accept(ctx)
        except Exception:
            accepted = False

        if accepted:
            try:
                return await opener.open(ctx)
            except Exception as e:
                errors.append(e)

    # Error management
    if not errors:
        raise OpenerError(f"No job result opener found for {ctx.job_results}")
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
