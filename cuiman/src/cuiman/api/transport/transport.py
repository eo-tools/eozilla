#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any

from ._result_sources import get_response_href
from .args import TransportArgs


class ResponseUriProvider:
    """Provide the response URI for a given source value."""

    def get_response_href(self, value: Any) -> str | None:
        """Return the effective response URI for a returned value, if retained.

        Deserialized results contain the response body but may lack its source
        URL. Readers need that URL as a base for relative references, including
        linked STAC metadata and links or Asset hrefs inside inline STAC documents.
        Custom transports may retain the effective URL after redirects without
        modifying the results by using the shared source registry. Associations
        registered by other transports are available here too. Returning None
        makes an unavailable base explicit; this lookup must not perform I/O.
        """
        return get_response_href(value)


class Transport(ResponseUriProvider, ABC):
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

    @abstractmethod
    def close(self):
        """Closes this transport."""


class AsyncTransport(ResponseUriProvider, ABC):
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

    @abstractmethod
    async def async_close(self):
        """Closes this transport."""


class TransportError(Exception):
    """Raised if an attempt to reach the server failed."""
