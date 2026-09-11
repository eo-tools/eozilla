# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""OIDC discovery trust checks, library claims validation, and loopback listener."""

import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx2
from authlib.oidc.core import CodeIDToken
from joserfc import jwt
from joserfc.jwk import KeySet, KeySetSerialization

from .config import OidcAuthConfig

CALLBACK_PATH = "/callback"
"""Path handled by the temporary OIDC loopback listener."""


def discovery_url(issuer_url: str) -> str:
    """Return the discovery URL for an HTTPS issuer."""
    _https_url(issuer_url)
    return f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"


def parse_oidc_discovery(response: httpx2.Response, issuer_url: str) -> dict[str, Any]:
    """Require an exact issuer match and HTTPS provider endpoints."""
    response.raise_for_status()
    metadata = response.json()
    if not isinstance(metadata, dict) or metadata.get("issuer") != issuer_url:
        raise ValueError("OIDC discovery issuer does not match the configured issuer.")
    for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        _https_url(metadata.get(name))
    if "revocation_endpoint" in metadata:
        _https_url(metadata["revocation_endpoint"])
    return metadata


def validate_id_token(
    auth: OidcAuthConfig,
    token: dict[str, Any],
    jwks: KeySetSerialization,
    nonce: str | None,
    *,
    initial: bool = False,
) -> None:
    """Verify the signature and OIDC claims with joserfc and Authlib.

    This public native client accepts asymmetric signatures; provider metadata
    cannot opt it into unsigned tokens or shared-secret signing.
    """
    decoded = jwt.decode(
        token["id_token"],
        KeySet.import_key_set(jwks),
        algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"],
    )
    claims = CodeIDToken(
        decoded.claims,
        decoded.header,
        options={
            "iss": {"value": str(auth.issuer_url)},
            "aud": {"value": auth.client_id},
        },
        params={
            "nonce": nonce if initial or "nonce" in decoded.claims else None,
            "client_id": auth.client_id,
            "access_token": token.get("access_token"),
        },
    )
    claims.validate(leeway=120)


def _https_url(value: Any) -> None:
    if not isinstance(value, str):
        raise ValueError("OIDC discovery requires HTTPS endpoints.")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("OIDC discovery requires HTTPS endpoints.")


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
            self.wfile.write(
                b"<p>Authorization response received. You may close this window.</p>"
            )

        def log_message(self, _format: str, *_args: object) -> None:
            """Suppress the temporary callback server's request logging."""

    return CallbackHandler
