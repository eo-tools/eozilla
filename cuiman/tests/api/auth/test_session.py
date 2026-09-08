#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import asyncio
import inspect
from unittest.mock import AsyncMock, Mock

import pytest

from cuiman.api.auth import (
    ApiKeyAuthConfig,
    BasicAuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    OAuth2AuthConfig,
    OidcAuthConfig,
    TokenAuthConfig,
    TokenResult,
    session,
)
from cuiman.api.auth.secret_store import SecretStoreError


def make_auth(kind, initial):
    values = {"access_token": None if initial else "old-access"}
    if kind == "oidc":
        return OidcAuthConfig(
            issuer_url="https://identity.example.test/realm",
            client_id="client",
            refresh_token="old-refresh",
            **values,
        )
    if kind == "password":
        return OAuth2AuthConfig(
            token_url="https://identity.example.test/token",
            refresh_token="old-refresh",
            **values,
        )
    return OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        grant_type="client_credentials",
        client_id="client",
        client_secret="secret",
        **values,
    )


def mock_protocol(monkeypatch, kind, asynchronous, **kwargs):
    name = {
        "oidc": "renew_oidc_tokens",
        "password": "renew_oauth2_tokens",
        "client_credentials": "obtain_oauth2_tokens",
    }[kind]
    if asynchronous:
        name += "_async"
    operation = (AsyncMock if asynchronous else Mock)(**kwargs)
    monkeypatch.setattr(session, name, operation)
    return operation


async def authenticate(auth, initial, asynchronous):
    if initial:
        operation = (
            session.resolve_auth_headers_async
            if asynchronous
            else session.resolve_auth_headers
        )
        result = operation(auth)
    else:
        factory = (
            session.make_async_token_refresher
            if asynchronous
            else session.make_token_refresher
        )
        result = factory(auth)()
    return await result if inspect.isawaitable(result) else result


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["password", "client_credentials", "oidc"])
@pytest.mark.parametrize("initial", [True, False])
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_token_commit_saves_before_publishing_and_preserves_state_on_failure(
    monkeypatch, kind, initial, asynchronous
):
    auth = make_auth(kind, initial)
    previous = auth.to_secret_dict()
    protocol = mock_protocol(
        monkeypatch,
        kind,
        asynchronous,
        return_value=TokenResult(
            access_token="new-access", refresh_token="new-refresh"
        ),
    )
    expected = {**previous, "access_token": "new-access"}
    if kind != "client_credentials":
        expected["refresh_token"] = "new-refresh"
    saved = []
    fail = True

    def persist(candidate):
        assert candidate is not auth
        assert candidate.to_secret_dict() == expected
        assert auth.to_secret_dict() == previous
        if fail:
            raise SecretStoreError("storage unavailable")
        saved.append(candidate.to_secret_dict())

    auth.set_secret_persistor(persist)
    with pytest.raises(SecretStoreError, match="storage unavailable"):
        await authenticate(auth, initial, asynchronous)
    assert auth.to_secret_dict() == previous
    assert saved == []

    # A later attempt is allowed. Whether the provider accepts an old refresh
    # token after rotation depends on its policy; no remote rollback is implied.
    fail = False
    headers = await authenticate(auth, initial, asynchronous)
    assert headers == {"Authorization": "Bearer new-access"}
    assert saved == [expected]
    assert auth.to_secret_dict() == expected
    assert protocol.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["password", "oidc"])
@pytest.mark.parametrize("initial", [True, False])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("refresh_token", [None, ""])
async def test_initial_login_and_refresh_preserve_an_unrotated_refresh_token(
    monkeypatch, kind, initial, asynchronous, refresh_token
):
    auth = make_auth(kind, initial)
    mock_protocol(
        monkeypatch,
        kind,
        asynchronous,
        return_value=TokenResult(
            access_token="new-access", refresh_token=refresh_token
        ),
    )
    await authenticate(auth, initial, asynchronous)
    assert auth.access_token == "new-access"
    assert auth.refresh_token == "old-refresh"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["password", "client_credentials", "oidc"])
@pytest.mark.parametrize("cancelled", [False, True])
async def test_failed_or_cancelled_renewal_does_not_publish_or_persist_tokens(
    monkeypatch, kind, cancelled
):
    auth = make_auth(kind, initial=False)
    previous = auth.to_secret_dict()
    persist = Mock()
    auth.set_secret_persistor(persist)
    error = asyncio.CancelledError if cancelled else RuntimeError
    mock_protocol(monkeypatch, kind, True, side_effect=error())

    with pytest.raises(error):
        await authenticate(auth, initial=False, asynchronous=True)
    assert auth.to_secret_dict() == previous
    persist.assert_not_called()


@pytest.mark.parametrize(
    "auth",
    [
        NoAuthConfig(),
        BasicAuthConfig(username="user", password="password"),
        ApiKeyAuthConfig(api_key="key"),
        TokenAuthConfig(access_token="injected-access"),
        LoginAuthConfig(login_url="https://identity.example.test/login"),
    ],
)
def test_non_renewable_auth_has_no_renewal_callback(auth):
    assert session.make_token_refresher(auth) is None
    assert session.make_async_token_refresher(auth) is None
