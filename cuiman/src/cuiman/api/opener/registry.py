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
        openers = list(self._openers)
        if not openers:
            raise OpenerError("No job result openers registered")

        errors: list[Exception] = []
        for opener in openers:
            if await opener.accept(ctx):
                try:
                    return await opener.open(ctx)
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
