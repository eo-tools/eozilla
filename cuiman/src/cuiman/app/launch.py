#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Cookie-authenticated processing-service proxy for Cuiman app launches.

The normal Eozilla App is a standalone SPA and may authenticate directly with
its configured processing service.  A Cuiman launch has a different trust
boundary: Cuiman already holds the processing-service credentials, so they
must not cross into the browser URL, JavaScript memory, or browser storage.

The launch protocol deliberately has only two browser-visible values::

    index.html?launch=<one-shot-code>
        -> POST ./_cuiman/launch
        -> HttpOnly session cookie
        -> requests to ./_cuiman/service/<processing-api-path>

The code is short-lived and consumed once.  The cookie selects an in-memory
session for the life of the Cuiman process.  That session contains only the
server-side upstream headers; the proxy adds them when it forwards a request.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
import remotestate as rs
from fastapi import FastAPI, HTTPException, Request, Response, status

from cuiman.api.auth import (
    LoginAuthConfig,
    OAuth2AuthConfig,
    login_async,
    obtain_oauth2_tokens_async,
)
from cuiman.api.config import ClientConfig

LAUNCH_QUERY_PARAM = "launch"
"""Name of the one-shot launch-code query parameter."""

LAUNCH_ENDPOINT = "/_cuiman/launch"
"""Same-origin endpoint that exchanges a launch code for a session."""

SERVICE_PROXY_ENDPOINT = "/_cuiman/service"
"""Same-origin prefix through which the app reaches the processing API."""

SESSION_COOKIE_NAME = "cuiman_app_session"
"""Name of the HttpOnly cookie that selects a launched app session."""

LAUNCH_CODE_TTL_SECONDS = 300
"""Lifetime of an unused browser bootstrap code."""

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_FORWARDED_REQUEST_HEADERS = ("accept", "content-type")
_HOP_BY_HOP_RESPONSE_HEADERS = frozenset(
    {
        "connection",
        "content-encoding",
        "content-length",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "set-cookie",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


@dataclass
class _LaunchCode:
    """Metadata used only to expire an unused one-shot browser code."""

    created_at: float


@dataclass
class _AppSession:
    """Server-only state selected by the browser's HttpOnly cookie."""

    headers: dict[str, str]


class LaunchedAppService(rs.Service[Any]):
    """Expose Cuiman's secure app-launch endpoints on a RemoteState server.

    This service intentionally owns its state in memory.  Cuiman launches one
    app server per client process, so persisting a browser session would add
    complexity without improving recovery: stopping Cuiman should invalidate
    the browser session as well.
    """

    def __init__(self, store: rs.Store[Any], client_config: ClientConfig) -> None:
        super().__init__(store)
        if not client_config.api_url:
            raise ValueError("Required setting 'api_url' not configured")
        self._client_config = client_config
        self._launch_codes: dict[str, _LaunchCode] = {}
        self._sessions: dict[str, _AppSession] = {}

    def create_launch_code(self) -> str:
        """Create a short-lived, single-use browser bootstrap code.

        The value is an opaque capability, not a session ID.  It is safe to put
        in the initial app URL only because it is high entropy, expires quickly,
        and cannot be used after the exchange endpoint consumes it.
        """
        self._remove_expired_launch_codes()
        launch_code = secrets.token_urlsafe(32)
        self._launch_codes[launch_code] = _LaunchCode(created_at=time.monotonic())
        return launch_code

    def _init_app(self, app: FastAPI) -> None:
        """Add the launch exchange and same-origin processing API proxy.

        ``remotestate`` calls this hook while it constructs the FastAPI app.
        Keeping these routes in the same app as the SPA is important for both
        local Cuiman and remote Jupyter Server Proxy launches: browser calls
        can stay relative to the app's visible URL and use a first-party cookie.
        """

        @app.middleware("http")
        async def add_security_headers(request: Request, call_next: Any) -> Response:
            """Prevent the launch code from being propagated as a referrer."""
            response = await call_next(request)
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        @app.post(LAUNCH_ENDPOINT, status_code=status.HTTP_204_NO_CONTENT)
        async def exchange_launch_code(request: Request, response: Response) -> None:
            """Consume a launch code and establish the browser's app session."""
            try:
                launch_code = _get_launch_code(await request.json())
            except ValueError as error:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
            self._consume_launch_code(launch_code)
            headers = await self._resolve_auth_headers()
            session_id = secrets.token_urlsafe(32)
            self._sessions[session_id] = _AppSession(headers=headers)
            response.set_cookie(
                SESSION_COOKIE_NAME,
                session_id,
                httponly=True,
                samesite="lax",
                secure=_get_request_scheme(request) == "https",
                path="/",
            )

        @app.api_route(
            f"{SERVICE_PROXY_ENDPOINT}/{{path:path}}",
            methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        )
        @app.api_route(
            SERVICE_PROXY_ENDPOINT,
            methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        )
        async def proxy_processing_service(request: Request, path: str = "") -> Response:
            """Forward a fixed processing-service path using session credentials."""
            if request.method in _UNSAFE_METHODS:
                _require_same_origin(request)
            session = self._get_session(request)
            return await self._proxy_request(request, path, session)

    def _consume_launch_code(self, launch_code: str) -> None:
        """Atomically invalidate an otherwise valid launch code."""
        self._remove_expired_launch_codes()
        if self._launch_codes.pop(launch_code, None) is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    def _remove_expired_launch_codes(self) -> None:
        """Discard codes that were never exchanged within the bootstrap window."""
        cutoff = time.monotonic() - LAUNCH_CODE_TTL_SECONDS
        for launch_code, launch in list(self._launch_codes.items()):
            if launch.created_at < cutoff:
                del self._launch_codes[launch_code]

    async def _resolve_auth_headers(self) -> dict[str, str]:
        """Resolve configured credentials without ever serializing them to the app.

        Login and OAuth configurations may start without an access token.  The
        first browser exchange triggers that resolution on Cuiman, then stores
        only the resulting request headers in the server session.  Static
        basic, token, API-key, and no-auth configurations already expose their
        headers through ``ClientConfig.auth_headers``.
        """
        auth = self._client_config.auth
        if isinstance(auth, LoginAuthConfig) and not auth.access_token:
            auth.access_token = await login_async(auth)
        elif isinstance(auth, OAuth2AuthConfig) and not auth.access_token:
            tokens = await obtain_oauth2_tokens_async(auth)
            auth.access_token = tokens.access_token
            auth.refresh_token = tokens.refresh_token
        return dict(self._client_config.auth_headers)

    def _get_session(self, request: Request) -> _AppSession:
        """Look up the server-only session selected by the HttpOnly cookie."""
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        session = self._sessions.get(session_id) if session_id else None
        if session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return session

    async def _proxy_request(
        self,
        request: Request,
        path: str,
        session: _AppSession,
    ) -> Response:
        """Forward once, refreshing OAuth credentials and retrying one 401 response."""
        upstream_response = await self._send_upstream(request, path, session.headers)
        if upstream_response.status_code == status.HTTP_401_UNAUTHORIZED:
            refresher = self._client_config._make_async_token_refresher()
            if refresher is not None:
                session.headers = await refresher()
                upstream_response = await self._send_upstream(
                    request, path, session.headers
                )
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers={
                name: value
                for name, value in upstream_response.headers.items()
                if name.lower() not in _HOP_BY_HOP_RESPONSE_HEADERS
            },
        )

    async def _send_upstream(
        self,
        request: Request,
        path: str,
        auth_headers: dict[str, str],
    ) -> httpx.Response:
        """Send a request to the fixed upstream API without trusting client auth.

        The browser may choose a processing API path, method, body, and query
        parameters, but never the upstream host or authentication headers.
        Only representation headers needed by the current SPA are forwarded.
        """
        headers = {
            name: request.headers[name]
            for name in _FORWARDED_REQUEST_HEADERS
            if name in request.headers
        }
        headers.update(auth_headers)
        async with httpx.AsyncClient(follow_redirects=False) as client:
            return await client.request(
                request.method,
                _get_upstream_url(self._client_config.api_url, path),
                params=list(request.query_params.multi_items()),
                content=await request.body(),
                headers=headers,
            )


def _get_launch_code(value: object) -> str:
    """Validate the minimal JSON payload accepted by the exchange endpoint."""
    if not isinstance(value, dict) or not isinstance(value.get("launch"), str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    launch_code = value["launch"]
    if not launch_code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return launch_code


def _require_same_origin(request: Request) -> None:
    """Reject cross-site unsafe requests made with the session cookie.

    The proxy forwards mutations such as process execution and job dismissal.
    SameSite cookies are helpful, but validating the browser origin provides a
    second explicit CSRF boundary for those operations.
    """
    expected_origin = _get_request_origin(request)
    origin = request.headers.get("origin")
    if origin == expected_origin:
        return
    referer = request.headers.get("referer")
    if referer and referer.startswith(f"{expected_origin}/"):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def _get_request_origin(request: Request) -> str:
    """Return the browser-visible origin, including reverse-proxy headers."""
    scheme = _get_request_scheme(request)
    host = request.headers.get(
        "x-forwarded-host", request.headers.get("host", request.url.netloc)
    )
    host = host.split(",", maxsplit=1)[0].strip()
    return f"{scheme}://{host}"


def _get_request_scheme(request: Request) -> str:
    """Use Jupyter/reverse-proxy HTTPS information when the backend is HTTP."""
    forwarded_scheme = request.headers.get("x-forwarded-proto")
    if forwarded_scheme:
        return forwarded_scheme.split(",", maxsplit=1)[0].strip()
    return request.url.scheme


def _get_upstream_url(api_url: str | None, path: str) -> str:
    """Append a browser-selected path to Cuiman's fixed processing API base URL.

    Parsing and reconstructing the URL keeps the configured origin and base
    path fixed.  Query strings and fragments in configuration are deliberately
    not inherited; request query parameters are forwarded separately.
    """
    assert api_url is not None
    parsed_api_url = urlsplit(api_url)
    encoded_path = quote(path, safe="/")
    base_path = parsed_api_url.path.rstrip("/")
    upstream_path = f"{base_path}/{encoded_path}" if encoded_path else base_path or "/"
    return urlunsplit(
        (
            parsed_api_url.scheme,
            parsed_api_url.netloc,
            upstream_path,
            "",
            "",
        )
    )
