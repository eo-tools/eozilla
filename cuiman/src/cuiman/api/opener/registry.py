#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable

from .opener import JobResultOpener


class JobResultOpenerRegistry:
    """A simple registry for job result openers."""

    def __init__(self):
        self._openers: list[JobResultOpener] = []

    @classmethod
    def create_default(cls) -> "JobResultOpenerRegistry":
        """Create a registry that includes default job result openers."""
        return JobResultOpenerRegistry()

    def clear(self) -> None:
        """Clears the registry.
        Removes all job result openers.
        """
        self._openers = []

    @property
    def openers(self) -> tuple[JobResultOpener, ...]:
        """The tuple registered of job result openers."""
        return tuple(self._openers)

    def register(self, opener: JobResultOpener) -> Callable[[], None]:
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
