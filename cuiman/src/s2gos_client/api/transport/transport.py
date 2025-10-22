#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any

from .args import TransportArgs


class Transport(ABC):
    """Abstraction of the transport that calls a web API in synchronous mode."""

    @abstractmethod
    def call(self, args: TransportArgs) -> Any:
        """
        Synchronously call a web API with the given endpoint
        `path`, `method`, `params`, etc. Then validate the response
        and return an instance of one of the types given by
        `return_types`.

        Args:
            args: The transport arguments.

        Returns:
            The response data of a successful web API call.

        Raises:
            TransportError: If an attempt to reach the server failed.
        """

    def close(self):
        """Closes this transport."""


class AsyncTransport(ABC):
    """Abstraction of the transport that calls a web API in asynchronous mode."""

    @abstractmethod
    async def async_call(self, args: TransportArgs) -> Any:
        """
        Asynchronously call a web API with the given endpoint
        `path`, `method`, `params`, etc. Then validate the response
        and return an instance of one of the types given by
        `return_types`.

        Args:
            args: The transport arguments.

        Returns:
            The response data of a successful web API call.

        Raises:
            TransportError: If an attempt to reach the server failed.
        """

    async def async_close(self):
        """Closes this transport."""


class TransportError(Exception):
    """Raised if an attempt to reach the server failed."""
