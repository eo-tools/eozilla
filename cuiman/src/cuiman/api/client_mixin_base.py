# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Shared client configuration, token snapshots, and local auth policy."""

import secrets
from abc import ABC, abstractmethod
from contextlib import contextmanager
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any, Callable, ClassVar, Generic, Iterator, TypeVar, cast

import httpx2
from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuth2Client

from .auth.config import (
    AuthConfig,
    LoginAuthConfig,
    OAuth2AuthConfig,
    OAuthTokenConfig,
    OidcAuthConfig,
    has_credentials,
)
from .auth.interactive import prompt_auth
from .auth.login import prepare_login, process_login_response
from .auth.oauth2_client import LoginRequiredError, oauth_options, save_credentials
from .auth.oidc import (
    LoopbackCallbackServer,
    discovery_url,
    parse_oidc_discovery,
    validate_id_token,
)
from .auth.secret_store import delete_auth_secrets
from .config import ClientConfig
from .transport.httpx2 import Httpx2Transport

_HttpClient = TypeVar("_HttpClient", httpx2.Client, httpx2.AsyncClient)


class ClientMixinBase(ABC, Generic[_HttpClient]):
    """Share local auth policy; Authlib owns OAuth tokens and protocol operations."""

    _async_mode: ClassVar[bool] = False
    _transport: Any
    _debug: bool

    @property
    def _config_path(self) -> Path:
        return ClientConfig.normalize_config_path(self.config._source_path)

    def _init_client_runtime(self) -> None:
        self._http_client: _HttpClient | None = None
        self._closed = False
        self._ready = False
        self._oidc_metadata: dict[str, Any] = {}
        self._oidc_nonce: str | None = (
            getattr(self.config.auth, "oauth_token", None) or {}
        ).get("_cuiman_nonce")

    @property
    @abstractmethod
    def config(self) -> ClientConfig:
        """Configuration supplied by the generated client."""

    @property
    def token(self) -> dict[str, Any] | None:
        """Return an independent snapshot of the live OAuth token, without login."""
        client = self._http_client
        return (
            deepcopy(dict(client.token))
            if isinstance(client, (OAuth2Client, AsyncOAuth2Client)) and client.token
            else None
        )

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("Client is closed. Create a new client to continue.")

    def _credentials(self, *, interactive: bool, force: bool) -> AuthConfig:
        auth = self.config.auth
        candidate: AuthConfig = auth
        if isinstance(auth, OAuthTokenConfig):
            client = self._http_client
            token = (
                client.token
                if isinstance(client, (OAuth2Client, AsyncOAuth2Client))
                else None
            ) or (auth.oauth_token if self._http_client is None else None)
            if token and not force:
                return auth
            if isinstance(auth, OidcAuthConfig):
                if not interactive:
                    raise LoginRequiredError(
                        "OpenID Connect requires an explicit client.login()."
                    )
                return auth
            candidate = auth.model_copy(update={"oauth_token": None})
        else:
            if self._ready and not force:
                return auth
            candidate = auth
        if not has_credentials(candidate) or (
            force and interactive and not isinstance(auth, OAuthTokenConfig)
        ):
            if not interactive:
                raise LoginRequiredError(
                    "Authentication requires login. Call client.login() (await it for AsyncClient), or use 'cuiman login'."
                )
            return auth.model_copy(update=prompt_auth(auth).model_dump())
        return auth

    def _configure_http_client(
        self, auth: AuthConfig, update_token: Callable[..., Any]
    ) -> None:
        self.config.auth = auth
        if self._http_client is None:
            if isinstance(auth, OAuthTokenConfig):
                factory = AsyncOAuth2Client if self._async_mode else OAuth2Client
                self._http_client = cast(
                    _HttpClient,
                    factory(**oauth_options(auth), update_token=update_token),
                )
            else:
                http_factory = httpx2.AsyncClient if self._async_mode else httpx2.Client
                self._http_client = cast(_HttpClient, http_factory())
        if isinstance(auth, OAuth2AuthConfig):
            client = self._http_client
            assert isinstance(client, (OAuth2Client, AsyncOAuth2Client))
            if client.client_secret != auth.client_secret:
                client.client_secret = auth.client_secret
                client.token_endpoint_auth_method = oauth_options(auth)[
                    "token_endpoint_auth_method"
                ]

    def _login_request(self, *, force: bool) -> Callable[[], Any] | None:
        """Bind the native client's initial grant or proprietary login request."""
        auth, client = self.config.auth, self._http_client
        if isinstance(auth, OAuth2AuthConfig):
            assert isinstance(client, (OAuth2Client, AsyncOAuth2Client))
            grant = (
                dict(username=auth.username, password=auth.password)
                if auth.grant_type == "password"
                else {}
            )
            return partial(client.fetch_token, **grant)
        if isinstance(auth, LoginAuthConfig) and (force or not auth.access_token):
            assert client is not None
            url, data = prepare_login(auth)
            return partial(client.request, "POST", url, data=data, auth=None)
        return None

    def _accept_login(self, response: Any, *, force: bool, save: bool) -> None:
        if isinstance(self.config.auth, LoginAuthConfig) and response is not None:
            self.config.auth.access_token = process_login_response(response)
        new_static_credentials = not isinstance(
            self.config.auth, OAuthTokenConfig
        ) and (not self._ready or force)
        if new_static_credentials or save or response is not None:
            self._save_credentials(required=save)
        self._ready = True

    @property
    def _discovery_url(self) -> str | None:
        auth = self.config.auth
        if isinstance(auth, OidcAuthConfig) and not self._oidc_metadata:
            return discovery_url(str(auth.issuer_url))
        return None

    def _accept_discovery(self, response: httpx2.Response) -> None:
        assert isinstance(self.config.auth, OidcAuthConfig)
        assert isinstance(self._http_client, (OAuth2Client, AsyncOAuth2Client))
        self._oidc_metadata = parse_oidc_discovery(
            response, str(self.config.auth.issuer_url)
        )
        self._http_client.metadata.update(self._oidc_metadata)

    @contextmanager
    def _oidc_validation(self, *, required: bool) -> Iterator[str | None]:
        """Invalidate rejected tokens, including a cancelled key fetch."""
        client = self._http_client
        if not isinstance(self.config.auth, OidcAuthConfig):
            yield None
            return
        assert isinstance(client, (OAuth2Client, AsyncOAuth2Client))
        try:
            client.token["_cuiman_nonce"] = self._oidc_nonce
            if not client.token.get("id_token"):
                if required:
                    raise ValueError("OIDC login response requires an ID token.")
                yield None
            else:
                yield self._oidc_metadata["jwks_uri"]
        except BaseException:
            client.token = None
            raise

    def _validate_id_token(self, response: httpx2.Response, *, required: bool) -> None:
        response.raise_for_status()
        auth, client = self.config.auth, self._http_client
        assert isinstance(auth, OidcAuthConfig)
        assert isinstance(client, (OAuth2Client, AsyncOAuth2Client))
        validate_id_token(
            auth, client.token, response.json(), self._oidc_nonce, initial=required
        )

    @property
    def _can_revoke(self) -> bool:
        return isinstance(self.config.auth, OidcAuthConfig) and bool(
            self.token or self.config.auth.oauth_token
        )

    def _save_credentials(self, *, required: bool = False) -> None:
        save_credentials(
            self.config.auth,
            self.token,
            config_path=self._config_path if required else None,
            api_url=self.config.api_url or "",
        )

    def _forget_credentials(self) -> None:
        try:
            delete_auth_secrets(self._config_path, self.config.api_url or "")
        finally:
            for name in self.config.auth.secret_fields:
                setattr(self.config.auth, name, None)
            if isinstance(self._http_client, (OAuth2Client, AsyncOAuth2Client)):
                self._http_client.token = None

    def _authorization(
        self, client: Any, server: LoopbackCallbackServer
    ) -> tuple[str, str, str]:
        client.redirect_uri = server.redirect_uri
        verifier = secrets.token_urlsafe(64)
        self._oidc_nonce = secrets.token_urlsafe(32)
        url, state = client.create_authorization_url(
            self._oidc_metadata["authorization_endpoint"],
            code_verifier=verifier,
            nonce=self._oidc_nonce,
        )
        return url, state, verifier

    def _revocation(self) -> dict[str, str] | None:
        token = self.token or getattr(self.config.auth, "oauth_token", None) or {}
        endpoint = self._oidc_metadata.get("revocation_endpoint")
        if not endpoint or not token:
            return None
        hint = "refresh_token" if token.get("refresh_token") else "access_token"
        return dict(url=endpoint, token=token[hint], token_type_hint=hint)

    def _get_transport(self) -> Any:
        self._require_open()
        if self._transport is None:
            self._transport = self._create_transport(
                **{
                    "async_request"
                    if self._async_mode
                    else "sync_request": self._request
                }
            )
        return self._transport

    @abstractmethod
    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Execute a request using the owned client in its I/O mode."""

    def _create_transport(self, **requesters: Any) -> Httpx2Transport:
        assert self.config.api_url is not None
        return Httpx2Transport(
            api_url=f"{self.config.api_url.rstrip('/')}/",
            return_type_map=self.config.return_type_map,
            debug=self._debug,
            **requesters,
        )

    def _request_options(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(self.config.auth, OAuthTokenConfig):
            headers = httpx2.Headers(self.config.auth.auth_headers)
            headers.update(kwargs.get("headers", {}))
            kwargs["headers"] = headers
        elif "authorization" in httpx2.Headers(kwargs.get("headers")):
            kwargs.setdefault("auth", None)
        return kwargs
