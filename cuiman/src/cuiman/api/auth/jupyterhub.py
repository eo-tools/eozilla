# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""HTTPX2 authentication using an upstream token owned by JupyterHub."""

import os
from collections.abc import Generator
from typing import Self, TypeGuard

import httpx2
from pydantic import HttpUrl


class JupyterHubAuthError(ValueError):
    """JupyterHub did not provide a usable upstream access token."""


class JupyterHubAuth(httpx2.Auth):
    """Retrieve a current upstream bearer token before each processing request.

    Args:
        hub_api_url: Trusted Hub API base URL, normally JUPYTERHUB_API_URL.
            Its /user endpoint must expose the owner's auth_state. HTTP is
            supported for private Hub networks; use HTTPS over untrusted links.
        hub_api_token: Hub credential authorized to read the owner's auth_state,
            normally JUPYTERHUB_API_TOKEN. It is sent only to the Hub lookup.

    Both arguments are explicit; construction performs no I/O or environment
    discovery. Attach this adapter only to clients for processing services that
    are trusted recipients of the upstream token. The Hub owns refresh; this
    adapter neither caches tokens nor retries processing requests. Both HTTPX2
    client modes execute the same flow on their existing owned connections.

    HTTP/transport errors propagate. Missing or malformed auth state raises
    JupyterHubAuthError without including the response body or credentials.
    """

    requires_response_body = True

    def __init__(self, *, hub_api_url: str, hub_api_token: str) -> None:
        try:
            url = httpx2.URL(str(HttpUrl(hub_api_url)))
        except (httpx2.InvalidURL, TypeError, ValueError):
            raise ValueError(
                "hub_api_url must be a valid HTTP(S) API base URL."
            ) from None
        if (
            url.scheme not in ("http", "https")
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "hub_api_url must be an HTTP(S) API base URL without "
                "credentials, a query, or a fragment."
            )
        if not _is_bearer_token(hub_api_token):
            raise ValueError("hub_api_token must be a nonempty ASCII bearer token.")
        self._user_url = httpx2.URL(str(url).rstrip("/") + "/user")
        self._hub_api_token = hub_api_token

    @classmethod
    def from_environment(cls, *, required: bool = False) -> Self | None:
        """Discover a Hub candidate without I/O; fail if required but absent.

        Both variables absent means no candidate. Partial or invalid values
        always raise a sanitized error. A candidate is only usable once the Hub
        successfully returns an upstream token during login or a request.
        """
        url = os.environ.get("JUPYTERHUB_API_URL")
        token = os.environ.get("JUPYTERHUB_API_TOKEN")
        if url is None and token is None and not required:
            return None
        if not url or not token:
            raise JupyterHubAuthError(
                "JupyterHub authentication requires both JUPYTERHUB_API_URL "
                "and JUPYTERHUB_API_TOKEN in the current server environment."
            )
        try:
            return cls(hub_api_url=url, hub_api_token=token)
        except ValueError as exc:
            raise JupyterHubAuthError(str(exc)) from None

    def auth_flow(
        self, request: httpx2.Request
    ) -> Generator[httpx2.Request, httpx2.Response, None]:
        """Look up auth state, then sign and send the original request once."""
        # Build from scratch: processing headers, cookies, body, and query must
        # not be forwarded to the Hub. Auth-flow requests bypass build_request,
        # so explicitly retain the owner's effective timeout.
        response = yield self._user_request(
            request.extensions.get("timeout", httpx2.Timeout(5).as_dict())
        )
        request.headers["Authorization"] = f"Bearer {self._access_token(response)}"
        yield request

    def _user_request(self, timeout: dict | None = None) -> httpx2.Request:
        return httpx2.Request(
            "GET",
            self._user_url,
            headers={
                "Authorization": f"Bearer {self._hub_api_token}",
                "Accept": "application/json",
            },
            extensions={"timeout": timeout} if timeout is not None else {},
        )

    def _access_token(self, response: httpx2.Response) -> str:
        response.raise_for_status()
        if response.history or response.url != self._user_url:
            raise JupyterHubAuthError("JupyterHub auth-state lookup was redirected.")
        try:
            user = response.json()
        except ValueError:
            raise JupyterHubAuthError(
                "JupyterHub auth-state response is not valid JSON."
            ) from None
        auth_state = user.get("auth_state") if isinstance(user, dict) else None
        if not isinstance(auth_state, dict):
            raise JupyterHubAuthError(
                "JupyterHub auth_state is unavailable. Enable auth state and grant "
                "the user and server roles admin:auth_state!user permission."
            )
        token = auth_state.get("access_token")
        if not _is_bearer_token(token):
            raise JupyterHubAuthError(
                "JupyterHub auth_state contains no usable upstream access_token. "
                "Check the Hub authenticator and sign in to JupyterHub again."
            )
        return token


def _is_bearer_token(value: object) -> TypeGuard[str]:
    """Reject empty tokens and characters that cannot safely form a header."""
    return (
        isinstance(value, str)
        and bool(value)
        and all(0x21 <= ord(char) <= 0x7E for char in value)
    )
