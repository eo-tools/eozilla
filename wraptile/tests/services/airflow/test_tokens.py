#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests

from wraptile.exceptions import ServiceException
from wraptile.services.airflow.tokens import (
    AirflowNativeTokenProvider,
    ClientCredentialsTokenProvider,
    TokenConfig,
    create_token_provider,
)

_OIDC_ENV = {
    "OIDC_TOKEN_URL": "https://idp.example/protocol/openid-connect/token",
    "OIDC_CLIENT_ID": "wraptile",
    "OIDC_CLIENT_SECRET": "s3cr3t",
}


def _token_response(token: str = "tok", expires_in: int = 300):  # noqa: S107
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"access_token": token, "expires_in": expires_in}
    return response


class ClientCredentialsTokenProviderTest(TestCase):
    @patch("wraptile.services.airflow.tokens.requests.post")
    def test_mints_token_and_caches_it(self, mock_post):
        mock_post.return_value = _token_response()
        provider = ClientCredentialsTokenProvider(
            token_url=_OIDC_ENV["OIDC_TOKEN_URL"],
            client_id="wraptile",
            client_secret="s3cr3t",  # noqa: S106
            audience="airflow",
        )

        self.assertEqual(provider.get_token(), "tok")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], _OIDC_ENV["OIDC_TOKEN_URL"])
        self.assertEqual(kwargs["data"]["grant_type"], "client_credentials")
        self.assertEqual(kwargs["data"]["client_id"], "wraptile")
        self.assertEqual(kwargs["data"]["client_secret"], "s3cr3t")
        self.assertEqual(kwargs["data"]["audience"], "airflow")

        # Second call is served from cache — no extra network round-trip.
        self.assertEqual(provider.get_token(), "tok")
        mock_post.assert_called_once()

    @patch("wraptile.services.airflow.tokens.requests.post")
    def test_refreshes_when_expired(self, mock_post):
        mock_post.side_effect = [_token_response("first"), _token_response("second")]
        provider = ClientCredentialsTokenProvider(
            token_url=_OIDC_ENV["OIDC_TOKEN_URL"], client_id="wraptile"
        )

        self.assertEqual(provider.get_token(), "first")
        provider._expiry = 0.0
        self.assertEqual(provider.get_token(), "second")
        self.assertEqual(mock_post.call_count, 2)

    @patch("wraptile.services.airflow.tokens.requests.post")
    def test_omits_secret_and_audience_when_unset(self, mock_post):
        mock_post.return_value = _token_response()
        ClientCredentialsTokenProvider(
            token_url=_OIDC_ENV["OIDC_TOKEN_URL"], client_id="public-client"
        ).get_token()

        data = mock_post.call_args.kwargs["data"]
        self.assertNotIn("client_secret", data)
        self.assertNotIn("audience", data)

    @patch("wraptile.services.airflow.tokens.requests.post")
    def test_http_error_becomes_service_exception(self, mock_post):
        response = MagicMock(status_code=401, reason="Unauthorized")
        response.raise_for_status.side_effect = requests.exceptions.HTTPError("nope")
        mock_post.return_value = response
        provider = ClientCredentialsTokenProvider(
            token_url=_OIDC_ENV["OIDC_TOKEN_URL"], client_id="wraptile"
        )

        with self.assertRaises(ServiceException) as ctx:
            provider.get_token()
        self.assertEqual(ctx.exception.status_code, 401)


class AirflowNativeTokenProviderTest(TestCase):
    @patch("wraptile.services.airflow.tokens.requests.post")
    def test_posts_credentials_to_auth_token(self, mock_post):
        mock_post.return_value = _token_response("airflow-native")
        provider = AirflowNativeTokenProvider(
            "http://airflow:8080",
            username="admin",
            password="pw",  # noqa: S106
        )

        self.assertEqual(provider.get_token(), "airflow-native")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://airflow:8080/auth/token")
        self.assertEqual(kwargs["json"], {"username": "admin", "password": "pw"})


class TokenConfigFromEnvTest(TestCase):
    def test_reads_oidc_settings(self):
        config = TokenConfig.from_env("http://airflow:8080", env=_OIDC_ENV)
        self.assertEqual(config.oidc_token_url, _OIDC_ENV["OIDC_TOKEN_URL"])
        self.assertEqual(config.oidc_client_id, "wraptile")
        self.assertEqual(config.oidc_client_secret, "s3cr3t")
        self.assertEqual(config.oidc_audience, "airflow")
        self.assertTrue(config.uses_client_credentials)

    def test_reads_airflow_settings(self):
        config = TokenConfig.from_env(
            "http://airflow:8080",
            env={"AIRFLOW_USERNAME": "svc", "AIRFLOW_PASSWORD": "pw"},
        )
        self.assertEqual(config.airflow_username, "svc")
        self.assertEqual(config.airflow_password, "pw")
        self.assertFalse(config.uses_client_credentials)

    def test_explicit_credentials_win_over_environment(self):
        config = TokenConfig.from_env(
            "http://airflow:8080",
            username="caller",
            password="caller-pw",  # noqa: S106
            env={"AIRFLOW_USERNAME": "svc", "AIRFLOW_PASSWORD": "pw"},
        )
        self.assertEqual(config.airflow_username, "caller")
        self.assertEqual(config.airflow_password, "caller-pw")

    def test_defaults_when_environment_is_empty(self):
        config = TokenConfig.from_env("http://airflow:8080", env={})
        self.assertEqual(config.airflow_username, "admin")
        self.assertIsNone(config.airflow_password)
        self.assertIsNone(config.oidc_token_url)
        self.assertEqual(config.oidc_audience, "airflow")

    @patch.dict("os.environ", _OIDC_ENV, clear=True)
    def test_defaults_to_os_environ(self):
        config = TokenConfig.from_env("http://airflow:8080")
        self.assertEqual(config.oidc_client_id, "wraptile")


class CreateTokenProviderTest(TestCase):
    def test_client_credentials_selected_when_configured(self):
        provider = TokenConfig(
            airflow_base_url="http://airflow:8080",
            oidc_token_url=_OIDC_ENV["OIDC_TOKEN_URL"],
            oidc_client_id="wraptile",
        ).create_token_provider()
        self.assertIsInstance(provider, ClientCredentialsTokenProvider)
        self.assertEqual(provider._audience, "airflow")

    def test_falls_back_to_native_provider(self):
        provider = TokenConfig(
            airflow_base_url="http://airflow:8080",
            airflow_password="pw",  # noqa: S106
        ).create_token_provider()
        self.assertIsInstance(provider, AirflowNativeTokenProvider)
        self.assertEqual(provider._username, "admin")

    def test_partial_oidc_config_is_rejected(self):
        # Without a client id there is nothing to authenticate as, so this must
        # not silently fall back to the native endpoint.
        config = TokenConfig(
            airflow_base_url="http://airflow:8080",
            oidc_token_url="https://idp.example",  # noqa: S106
            airflow_password="pw",  # noqa: S106
        )
        with self.assertRaises(RuntimeError) as ctx:
            config.create_token_provider()
        self.assertIn("incomplete OIDC configuration", str(ctx.exception))

    def test_native_provider_requires_password(self):
        config = TokenConfig(airflow_base_url="http://airflow:8080")
        with self.assertRaises(RuntimeError):
            config.create_token_provider()

    @patch.dict("os.environ", _OIDC_ENV, clear=True)
    def test_module_function_reads_the_environment(self):
        provider = create_token_provider("http://airflow:8080")
        self.assertIsInstance(provider, ClientCredentialsTokenProvider)
