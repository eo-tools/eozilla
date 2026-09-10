# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Shared client state and transport configuration, independent of I/O mode."""

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Awaitable, Callable, Generic, TypeVar

from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuth2Client

from .auth.config import OAuth2AuthConfig
from .config import ClientConfig
from .transport.httpx2 import Httpx2Transport

_OAuthClient = TypeVar("_OAuthClient", OAuth2Client, AsyncOAuth2Client)


class ClientMixinBase(ABC, Generic[_OAuthClient]):
    """Share token snapshots and transport setup between sync and async clients."""

    _debug: bool

    def _init_client_runtime(self) -> None:
        self._oauth_client: _OAuthClient | None = None

    @property
    @abstractmethod
    def config(self) -> ClientConfig:
        """Will be overridden by the generated client class."""

    @property
    def token(self) -> dict[str, Any] | None:
        """Return an independent snapshot of the live OAuth2 token.

        Reading this property never starts authentication. Other authentication
        mechanisms currently retain their configuration-based token interface.
        """
        return (
            deepcopy(dict(self._oauth_client.token))
            if self._oauth_client and self._oauth_client.token
            else None
        )

    def _create_transport(
        self,
        *,
        token_refresher: Callable[[], dict[str, str]] | None = None,
        async_token_refresher: Callable[[], Awaitable[dict[str, str]]] | None = None,
    ) -> Httpx2Transport:
        assert self.config.api_url is not None
        auth_header = None
        if self._oauth_client is not None:
            auth = self.config.auth
            assert isinstance(auth, OAuth2AuthConfig)
            auth_header = (
                "Authorization" if auth.use_bearer else auth.access_token_header
            )
        return Httpx2Transport(
            api_url=f"{self.config.api_url.rstrip('/')}/",
            headers=self.config.auth_headers if self._oauth_client is None else None,
            return_type_map=self.config.return_type_map,
            token_refresher=token_refresher,
            async_token_refresher=async_token_refresher,
            debug=self._debug,
            sync_httpx2=(
                self._oauth_client
                if isinstance(self._oauth_client, OAuth2Client)
                else None
            ),
            async_httpx2=(
                self._oauth_client
                if isinstance(self._oauth_client, AsyncOAuth2Client)
                else None
            ),
            auth_header=auth_header,
        )
