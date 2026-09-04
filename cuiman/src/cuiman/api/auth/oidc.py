#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0 License.

"""OpenID Connect discovery, PKCE, and loopback callback helpers."""

import base64
import hashlib
import queue
import secrets
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlsplit, urlunsplit

import httpx

from .config import OidcAuthConfig
from .login import TokenResult
from .oauth2 import process_oauth2_token_response

CALLBACK_PATH = "/callback"
"""The path handled by the temporary OIDC loopback callback server."""


@dataclass(frozen=True)
class OidcDiscovery:
    """Authorization-server endpoints obtained through OIDC discovery."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    revocation_endpoint: str | None = None


def discovery_url(issuer_url: str) -> str:
    """Return the OpenID Connect discovery URL for an issuer."""
    issuer = urlsplit(issuer_url)
    path = issuer.path.rstrip("/")
    return urlunsplit(
        (
            issuer.scheme,
            issuer.netloc,
            f"/.well-known/openid-configuration{path}",
            "",
            "",
        )
    )


def discover_oidc_provider(auth_config: OidcAuthConfig) -> OidcDiscovery:
    """Discover and validate the configured OpenID Connect provider."""
    issuer_url, metadata_url = prepare_oidc_discovery(auth_config)
    with httpx.Client() as client:
        response = client.get(metadata_url)
    return parse_oidc_discovery(response, issuer_url)


def parse_oidc_discovery(response: httpx.Response, issuer_url: str) -> OidcDiscovery:
    """Validate OpenID Connect discovery metadata from a provider response."""
    response.raise_for_status()
    metadata: Any = response.json()
    if not isinstance(metadata, dict):
        raise RuntimeError("OIDC discovery response must be a JSON object.")
    issuer = metadata.get("issuer")
    if issuer != issuer_url:
        raise RuntimeError(
            "OIDC discovery issuer does not match the configured issuer."
        )
    authorization_endpoint = _required_https_url(metadata, "authorization_endpoint")
    token_endpoint = _required_https_url(metadata, "token_endpoint")
    revocation_endpoint = _optional_https_url(metadata, "revocation_endpoint")
    return OidcDiscovery(
        issuer=issuer,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        revocation_endpoint=revocation_endpoint,
    )


def prepare_oidc_discovery(auth_config: OidcAuthConfig) -> tuple[str, str]:
    """Return the configured issuer and its OIDC discovery metadata URL."""
    issuer_url = str(auth_config.issuer_url)
    return issuer_url, discovery_url(issuer_url)


def generate_pkce_verifier() -> str:
    """Generate a high-entropy verifier for an S256 PKCE authorization flow."""
    return secrets.token_urlsafe(64)


def pkce_challenge(verifier: str) -> str:
    """Return the S256 PKCE challenge for a verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_authorization_url(
    discovery: OidcDiscovery,
    auth_config: OidcAuthConfig,
    redirect_uri: str,
    state: str,
    verifier: str,
) -> str:
    """Build an OIDC Authorization Code request using PKCE."""
    parameters = {
        "response_type": "code",
        "client_id": auth_config.client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(auth_config.scopes),
        "state": state,
        "code_challenge": pkce_challenge(verifier),
        "code_challenge_method": "S256",
    }
    return f"{discovery.authorization_endpoint}?{urlencode(parameters)}"


def parse_callback_parameters(parameters: dict[str, list[str]], state: str) -> str:
    """Validate an authorization callback and return its authorization code."""
    error = _single_callback_value(parameters, "error")
    if error is not None:
        description = _single_callback_value(parameters, "error_description")
        message = f"OIDC authorization failed: {error}"
        if description:
            message = f"{message}: {description}"
        raise RuntimeError(message)
    callback_state = _single_callback_value(parameters, "state")
    if callback_state != state:
        raise RuntimeError(
            "OIDC callback state does not match the authorization request."
        )
    code = _single_callback_value(parameters, "code")
    if not code:
        raise RuntimeError("OIDC callback does not contain an authorization code.")
    return code


def exchange_oidc_code(
    discovery: OidcDiscovery,
    auth_config: OidcAuthConfig,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> TokenResult:
    """Exchange an authorization code for access and refresh tokens."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": auth_config.client_id,
        "code_verifier": verifier,
    }
    with httpx.Client() as client:
        response = client.post(discovery.token_endpoint, data=data)
    return process_oauth2_token_response(response)


def renew_oidc_tokens(auth_config: OidcAuthConfig) -> TokenResult:
    """Refresh an OIDC access token using its stored refresh token."""
    data = prepare_oidc_refresh_request(auth_config)
    discovery = discover_oidc_provider(auth_config)
    with httpx.Client() as client:
        response = client.post(discovery.token_endpoint, data=data)
    return process_oauth2_token_response(response)


def prepare_oidc_refresh_request(
    auth_config: OidcAuthConfig,
) -> dict[str, str]:
    """Build the token request for refreshing an OIDC access token."""
    if not auth_config.refresh_token:
        raise ValueError("An OIDC refresh token is required to renew the access token.")
    return {
        "grant_type": "refresh_token",
        "refresh_token": auth_config.refresh_token,
        "client_id": auth_config.client_id,
    }


class LoopbackCallbackServer:
    """Receive one OIDC authorization response through a local loopback URI."""

    def __init__(self, callback_path: str = CALLBACK_PATH) -> None:
        """Create an unstarted callback server bound to an ephemeral port."""
        self._callback_path = callback_path
        self._parameters: queue.Queue[dict[str, list[str]]] = queue.Queue(maxsize=1)
        handler = _make_callback_handler(callback_path, self._parameters)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def redirect_uri(self) -> str:
        """Return the redirect URI registered in the authorization request."""
        return f"http://127.0.0.1:{self._server.server_port}{self._callback_path}"

    def start(self) -> None:
        """Start receiving callbacks in a background thread."""
        self._thread.start()

    def wait_for_callback(self, timeout: float) -> dict[str, list[str]]:
        """Wait for callback query parameters or raise on timeout."""
        try:
            return self._parameters.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError(
                "Timed out waiting for the OIDC authorization callback."
            ) from exc

    def close(self) -> None:
        """Stop the callback server and release its loopback port."""
        self._server.shutdown()
        self._server.server_close()
        if self._thread.is_alive():
            self._thread.join()

    def __enter__(self) -> "LoopbackCallbackServer":
        """Start the callback server for a context-managed authorization flow."""
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        """Stop the callback server after the authorization flow ends."""
        self.close()


def _required_https_url(metadata: dict[str, Any], name: str) -> str:
    value = metadata.get(name)
    if not isinstance(value, str) or urlparse(value).scheme != "https":
        raise RuntimeError(f"OIDC discovery must contain an HTTPS {name}.")
    return value


def _optional_https_url(metadata: dict[str, Any], name: str) -> str | None:
    if name not in metadata:
        return None
    return _required_https_url(metadata, name)


def _single_callback_value(parameters: dict[str, list[str]], name: str) -> str | None:
    values = parameters.get(name, [])
    if len(values) > 1:
        raise RuntimeError(f"OIDC callback contains multiple {name} values.")
    return values[0] if values else None


def _make_callback_handler(
    callback_path: str,
    parameters: queue.Queue[dict[str, list[str]]],
) -> type[BaseHTTPRequestHandler]:
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != callback_path:
                self.send_error(404)
                return
            try:
                parameters.put_nowait(parse_qs(parsed.query, keep_blank_values=True))
            except queue.Full:
                self.send_error(409)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<p>Login completed. You may close this window.</p>")

        def log_message(self, _format: str, *_args: object) -> None:
            """Suppress the temporary callback server's request logging."""

    return CallbackHandler
