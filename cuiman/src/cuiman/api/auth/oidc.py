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
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .config import OidcAuthConfig
from .oauth2 import process_oauth2_token_response
from .tokens import TokenResult

CALLBACK_PATH = "/callback"
"""The path handled by the temporary OIDC loopback callback server."""


@dataclass(frozen=True)
class OidcDiscovery:
    """Validated authorization-server endpoints obtained through OIDC discovery.

    The authorization and token endpoints are required. The revocation endpoint
    is optional because OIDC providers are not required to publish one.
    """

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    revocation_endpoint: str | None = None


def discovery_url(issuer_url: str) -> str:
    """Return an issuer's OpenID Connect discovery metadata URL.

    Args:
        issuer_url: The issuer identifier, including any realm or tenant path,
            rather than an authorization or token endpoint.
    """
    return f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"


def discover_oidc_provider(auth_config: OidcAuthConfig) -> OidcDiscovery:
    """Fetch and validate the configured OpenID Connect provider's metadata.

    Raises:
        ValueError: If discovery cannot be fetched or does not describe the
            configured issuer and required HTTPS endpoints.
    """
    issuer_url, metadata_url = prepare_oidc_discovery(auth_config)
    try:
        with httpx.Client() as client:
            response = client.get(metadata_url)
        return parse_oidc_discovery(response, issuer_url)
    except httpx.HTTPStatusError as exc:
        detail = f"HTTP {exc.response.status_code} {exc.response.reason_phrase}"
        raise _discovery_error(issuer_url, metadata_url, detail) from exc
    except httpx.HTTPError as exc:
        detail = str(exc) or type(exc).__name__
        raise _discovery_error(issuer_url, metadata_url, detail) from exc
    except (RuntimeError, ValueError) as exc:
        detail = str(exc)
        raise _discovery_error(issuer_url, metadata_url, detail) from exc


def _discovery_error(issuer_url: str, metadata_url: str, detail: str) -> ValueError:
    """Create a concise, user-facing OIDC discovery error."""
    return ValueError(
        "OIDC discovery failed for issuer "
        f"'{issuer_url}' at '{metadata_url}': {detail}. "
        "Check that the issuer URL is correct and serves OIDC discovery metadata."
    )


def parse_oidc_discovery(response: httpx.Response, issuer_url: str) -> OidcDiscovery:
    """Validate OpenID Connect discovery metadata from a provider response.

    The returned issuer must equal ``issuer_url`` and the authorization and
    token endpoints must use HTTPS.
    """
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
    """Build an OIDC Authorization Code request using S256 PKCE and state.

    ``redirect_uri`` must match the URI used in :func:`exchange_oidc_code`.
    ``state`` is caller-provided because the caller must retain it until the
    browser returns to the callback.
    """
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
    """Validate an authorization callback and return its single code value.

    Provider errors, duplicate parameters, a missing code, and a mismatched
    state are rejected before an authorization code can be exchanged.
    """
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
    """Exchange an authorization code for access and optional refresh tokens.

    This completes the Authorization Code flow. The client ID, redirect URI,
    and PKCE verifier must be the values used to create the authorization URL.
    """
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
    """Refresh an OIDC access token using its stored refresh token.

    Callers that loaded credentials from the CLI keyring should persist any
    rotated refresh token returned by the provider.
    """
    data = prepare_oidc_refresh_request(auth_config)
    discovery = discover_oidc_provider(auth_config)
    with httpx.Client() as client:
        response = client.post(discovery.token_endpoint, data=data)
    return process_oauth2_token_response(response)


def revoke_oidc_tokens(auth_config: OidcAuthConfig) -> bool:
    """Revoke a stored OIDC token when the provider publishes an endpoint.

    A refresh token is preferred; otherwise the access token is used. Returns
    ``False`` without making a revocation request when neither token is present
    or the provider does not advertise a revocation endpoint.
    """
    token = auth_config.refresh_token or auth_config.access_token
    if not token:
        return False
    discovery = discover_oidc_provider(auth_config)
    if discovery.revocation_endpoint is None:
        return False
    data = {
        "token": token,
        "token_type_hint": (
            "refresh_token" if auth_config.refresh_token else "access_token"
        ),
        "client_id": auth_config.client_id,
    }
    with httpx.Client() as client:
        response = client.post(discovery.revocation_endpoint, data=data)
    response.raise_for_status()
    return True


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
    """Receive one OIDC authorization response through a local loopback URI.

    The server binds only to ``127.0.0.1`` on an ephemeral port and handles one
    request at ``/callback`` by default. Register the resulting redirect URI
    pattern with the OIDC client before starting an authorization flow.
    """

    def __init__(self, callback_path: str = CALLBACK_PATH) -> None:
        """Create an unstarted callback server bound to an ephemeral port."""
        self._callback_path = callback_path
        self._parameters: queue.Queue[dict[str, list[str]]] = queue.Queue(maxsize=1)
        handler = _make_callback_handler(callback_path, self._parameters)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def redirect_uri(self) -> str:
        """Return this server's ephemeral loopback redirect URI."""
        return f"http://127.0.0.1:{self._server.server_port}{self._callback_path}"

    def start(self) -> None:
        """Start receiving the single callback in a background thread."""
        self._thread.start()

    def wait_for_callback(self, timeout: float) -> dict[str, list[str]]:
        """Wait for callback query parameters or raise ``TimeoutError``."""
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
