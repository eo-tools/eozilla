#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Bearer tokens for the wraptile->airflow hop.

Two ways to obtain one, selected by :meth:`TokenConfig.create_token_provider`:

* :class:`ClientCredentialsTokenProvider` — the OAuth2 ``client_credentials``
  grant against any OIDC-compliant identity provider. The resulting token is
  what the gateway in front of Airflow validates (issuer, audience, roles).
* :class:`AirflowNativeTokenProvider` — Airflow's own ``/auth/token`` endpoint,
  the fallback for deployments without a gateway in the path.

The environment is read in exactly one place, :meth:`TokenConfig.from_env`;
everything downstream of it takes a :class:`TokenConfig` and is testable
without touching ``os.environ``.

Nothing here is specific to a particular identity provider: only the standard
OAuth2 token endpoint and grant are used.
"""

import abc
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

import requests

from wraptile.exceptions import ServiceException

# Re-mint the service token this many seconds before it expires, so a request
# never carries an already-expired bearer (a typical provider TTL is 300s).
TOKEN_REFRESH_MARGIN = 30

# Used when the token response omits "expires_in".
DEFAULT_TOKEN_LIFETIME = 300

TOKEN_REQUEST_TIMEOUT = 10

DEFAULT_AUDIENCE = "airflow"

DEFAULT_AIRFLOW_USERNAME = "admin"


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


@dataclass(frozen=True)
class TokenConfig:
    """Everything needed to decide *how* to obtain an Airflow bearer token.

    Construct it directly in tests, or via :meth:`from_env` in production.
    The OIDC path wins whenever it is configured; the Airflow-native path is
    the fallback.
    """

    airflow_base_url: str
    oidc_token_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_audience: str = DEFAULT_AUDIENCE
    airflow_username: str = DEFAULT_AIRFLOW_USERNAME
    airflow_password: Optional[str] = None

    @classmethod
    def from_env(
        cls,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        env: Optional[Mapping[str, str]] = None,
        # Airflow credentials passed by the caller take precedence over the
        # environment; the OIDC settings are environment-only (deployment
        # decides whether a gateway is in the path, not the call site).
    ) -> "TokenConfig":
        """Read the token settings from a mapping, `os.environ` by default.

        Args:
            base_url: Base URL of the Airflow web API, used by the native
                fallback.
            username: Airflow username, defaults to env `AIRFLOW_USERNAME`,
                then `admin`.
            password: Airflow password, defaults to env `AIRFLOW_PASSWORD`.
            env: The environment to read; injected by tests.
        """
        env = os.environ if env is None else env
        return cls(
            airflow_base_url=base_url,
            oidc_token_url=env.get("OIDC_TOKEN_URL") or None,
            oidc_client_id=env.get("OIDC_CLIENT_ID") or None,
            oidc_client_secret=env.get("OIDC_CLIENT_SECRET") or None,
            oidc_audience=env.get("OIDC_AUDIENCE") or DEFAULT_AUDIENCE,
            airflow_username=(
                username or env.get("AIRFLOW_USERNAME") or DEFAULT_AIRFLOW_USERNAME
            ),
            airflow_password=password or env.get("AIRFLOW_PASSWORD") or None,
        )

    @property
    def uses_client_credentials(self) -> bool:
        """Whether the OIDC client-credentials grant is configured at all."""
        return bool(self.oidc_token_url or self.oidc_client_id)

    def create_token_provider(self) -> TokenProvider:
        """Build the token provider this configuration selects.

        Raises:
            RuntimeError: If the OIDC settings are only half-filled, or if the
                native fallback has no Airflow password.
        """
        if self.uses_client_credentials:
            if not (self.oidc_token_url and self.oidc_client_id):
                # Half-configuring OIDC is a deployment mistake. Falling back to
                # the native endpoint here would paper over it and send Airflow
                # a token the gateway was meant to validate.
                raise RuntimeError(
                    "incomplete OIDC configuration; please set both env vars"
                    " OIDC_TOKEN_URL and OIDC_CLIENT_ID"
                )
            return ClientCredentialsTokenProvider(
                token_url=self.oidc_token_url,
                client_id=self.oidc_client_id,
                client_secret=self.oidc_client_secret,
                audience=self.oidc_audience,
            )

        if not self.airflow_password:
            raise RuntimeError(
                "missing Airflow password; please set env var AIRFLOW_PASSWORD"
            )
        return AirflowNativeTokenProvider(
            self.airflow_base_url,
            username=self.airflow_username,
            password=self.airflow_password,
        )


def create_token_provider(
    base_url: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> TokenProvider:
    """Select the token provider from the environment.

    Convenience wrapper over ``TokenConfig.from_env(...).create_token_provider()``.
    """
    return TokenConfig.from_env(
        base_url, username=username, password=password
    ).create_token_provider()


def _json_or_raise(response: requests.Response) -> dict:
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise ServiceException(
            response.status_code, detail=response.reason or str(e), exception=e
        ) from e
    return response.json()
