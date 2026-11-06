#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any

from .args import TransportArgs


class Transport(ABC):
    """Abstraction of the transport that calls a web API in synchronous mode."""

    def get_response_href(self, value: Any) -> str | None:
        """Return the effective response URI for a returned value, if retained.

        Deserialized results contain the response body but may lack its source
        URL. Readers need that URL as a base for relative references, including
        linked STAC metadata and links or Asset hrefs inside inline STAC documents.
        Custom transports may retain the effective URL after redirects without
        modifying the results. Returning None makes an unavailable base explicit;
        this lookup must not perform I/O.
        """
        return None

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

    @abstractmethod
    def close(self):
        """Closes this transport."""


class AsyncTransport(ABC):
    """Abstraction of the transport that calls a web API in asynchronous mode."""

    def get_response_href(self, value: Any) -> str | None:
        """Return a retained effective response URI without performing I/O.

        This supplies the source URL missing from deserialized results so readers
        can resolve relative STAC metadata links and Asset hrefs. Retain the
        effective URL after redirects without modifying the results; return None
        when no source URL is available.
        """
        return None

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

    @abstractmethod
    async def async_close(self):
        """Closes this transport."""


class TransportError(Exception):
    """Raised if an attempt to reach the server failed."""
