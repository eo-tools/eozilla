#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Bearer tokens for the wraptile->airflow hop.

Two ways to obtain one, selected by :func:`create_token_provider`:

* :class:`ClientCredentialsTokenProvider` — the OAuth2 ``client_credentials``
  grant against any OIDC-compliant identity provider. The resulting token is
  what the gateway in front of Airflow validates (issuer, audience, roles).
* :class:`AirflowNativeTokenProvider` — Airflow's own ``/auth/token`` endpoint,
  the fallback for deployments without a gateway in the path.

Nothing here is specific to a particular identity provider: only the standard
OAuth2 token endpoint and grant are used.
"""

import abc
import os
import time
from typing import Optional

import requests

from wraptile.exceptions import ServiceException

# Re-mint the service token this many seconds before it expires, so a request
# never carries an already-expired bearer (a typical provider TTL is 300s).
TOKEN_REFRESH_MARGIN = 30

# Used when the token response omits "expires_in".
DEFAULT_TOKEN_LIFETIME = 300

TOKEN_REQUEST_TIMEOUT = 10


class TokenProvider(abc.ABC):
    """Supplies the bearer token for calls to the Airflow API."""

    @abc.abstractmethod
    def get_token(self) -> str:
        """Return a currently valid access token."""


class ClientCredentialsTokenProvider(TokenProvider):
    """OAuth2 ``client_credentials`` grant against an OIDC provider.

    The token is cached and re-minted shortly before expiry so it is not
    re-fetched on every request.
    """

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: Optional[str] = None,
        audience: Optional[str] = None,
    ):
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._audience = audience
        self._token: Optional[str] = None
        self._expiry: float = 0.0

    def get_token(self) -> str:
        now = time.monotonic()
        if self._token and now < self._expiry:
            return self._token

        data = {"grant_type": "client_credentials", "client_id": self._client_id}
        if self._client_secret:
            data["client_secret"] = self._client_secret
        if self._audience:
            # The client's audience mapper normally stamps this already;
            # sending it explicitly is harmless and defensive.
            data["audience"] = self._audience

        response = requests.post(
            self._token_url, data=data, timeout=TOKEN_REQUEST_TIMEOUT
        )
        token_data = _json_or_raise(response)
        self._token = token_data["access_token"]
        self._expiry = (
            now
            + token_data.get("expires_in", DEFAULT_TOKEN_LIFETIME)
            - TOKEN_REFRESH_MARGIN
        )
        return self._token


class AirflowNativeTokenProvider(TokenProvider):
    """Airflow's own ``/auth/token`` endpoint, authenticated by password."""

    def __init__(self, base_url: str, username: str, password: str):
        self._base_url = base_url
        self._username = username
        self._password = password

    def get_token(self) -> str:
        response = requests.post(
            f"{self._base_url}/auth/token",
            json={"username": self._username, "password": self._password},
            timeout=TOKEN_REQUEST_TIMEOUT,
        )
        return _json_or_raise(response)["access_token"]


def create_token_provider(
    base_url: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> TokenProvider:
    """Select the token provider from the environment.

    Uses the client-credentials grant when `OIDC_TOKEN_URL` and `OIDC_CLIENT_ID`
    are both set, otherwise falls back to Airflow's native token endpoint.

    Args:
        base_url: Base URL of the Airflow web API, used by the native fallback.
        username: Airflow username, defaults to env `AIRFLOW_USERNAME`/`admin`.
        password: Airflow password, defaults to env `AIRFLOW_PASSWORD`.

    Raises:
        RuntimeError: In the fallback case, if no Airflow password is available.
    """
    token_url = os.getenv("OIDC_TOKEN_URL")
    client_id = os.getenv("OIDC_CLIENT_ID")
    if token_url and client_id:
        return ClientCredentialsTokenProvider(
            token_url=token_url,
            client_id=client_id,
            client_secret=os.getenv("OIDC_CLIENT_SECRET"),
            audience=os.getenv("OIDC_AUDIENCE", "airflow"),
        )

    username = username or os.getenv("AIRFLOW_USERNAME") or "admin"
    password = password or os.getenv("AIRFLOW_PASSWORD")
    if not password:
        raise RuntimeError(
            "missing Airflow password; please set env var AIRFLOW_PASSWORD"
        )
    return AirflowNativeTokenProvider(base_url, username=username, password=password)


def _json_or_raise(response: requests.Response) -> dict:
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise ServiceException(
            response.status_code, detail=response.reason or str(e), exception=e
        ) from e
    return response.json()
