#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable

from .opener import Opener, OpenerContext

from typing import Any


class OpenerError(RuntimeError):
    """A job result could not be opened.

    This error is potentially raised by the
    [OpenerRegistry.open_result()][OpenerRegistry.open_result]
    method.
    """


class OpenerRegistry:
    """A simple registry for job result openers."""

    def __init__(self):
        self._openers = []

    @classmethod
    def create_default(cls) -> "OpenerRegistry":
        """Create a registry that includes default job result openers."""
        return OpenerRegistry()

    def clear(self) -> None:
        """Clears the registry.
        Removes all job result openers.
        """
        self._openers = []

    @property
    def openers(self) -> tuple[Opener, ...]:
        """The tuple registered of job result openers."""
        return tuple(self._openers)

    def register(self, opener: Opener) -> Callable[[], None]:
        """Register a job result opener.

        Args:
            opener: The opener.

        Returns:
            A function that can be called to unregister the opener.
        """

        def unregister():
            try:
                self._openers.remove(opener)
            except ValueError:
                pass

        # Insert at the beginning so that openers
        # added last are used first.
        self._openers.insert(0, opener)
        return unregister

    async def open_result(self, ctx: OpenerContext) -> Any:
        """
        Open a job result.

        The method iterates registered openers to find any opener
        that accepts the given `ctx`, and if so, will open it
        without raising.
        Last added openers are used first.

        Args:
            ctx: The context used by the openers to check whether
                an output can be opened and, if so, to open it.

        Returns:
            The result of opening a job result.

        Raises:
            OpenerError: If the `ctx` object could not be opened.
        """
        return await _open_result(ctx, *self._openers)


async def _open_result(ctx: OpenerContext, *openers: Opener) -> Any:
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
