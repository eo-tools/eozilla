"""Runtime auth precedence through real sync/async clients and mock HTTP."""

import inspect
from unittest.mock import Mock

import httpx2
import pytest

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import LoginRequiredError, TokenAuthConfig
from cuiman.api.exceptions import ClientError


class MutableAuth(httpx2.Auth):
    """Sign with a changeable credential without storing it in configuration."""

    def __init__(self):
        self.value = "first"
        self.calls = 0

    def auth_flow(self, request):
        self.calls += 1
        request.headers["Authorization"] = f"Bearer {self.value}"
        yield request


async def invoke(method, *args, **kwargs):
    result = method(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


@pytest.fixture(params=[Client, AsyncClient], ids=["sync", "async"])
def kind(request):
    return request.param


AUTH_CONFIGS = [
    {"auth_type": "none"},
    {"auth_type": "basic"},
    {"auth_type": "token"},
    {"auth_type": "api-key"},
    {"auth_type": "api-key", "api_key": "configured-key"},
    {
        "auth_type": "token",
        "access_token": "configured-token",
        "access_token_header": "X-Auth-Token",
    },
    {"auth_type": "login", "login_url": "https://identity.test/login"},
    {
        "auth_type": "oauth2",
        "token_url": "https://identity.test/token",
        "client_id": "client",
    },
    {
        "auth_type": "oidc",
        "issuer_url": "https://identity.test/realm",
        "client_id": "client",
    },
    {
        "auth_type": "oauth2",
        "token_url": "https://identity.test/token",
        "client_id": "client",
        "oauth_token": {
            "access_token": "expired",
            "refresh_token": "unused-refresh",
            "expires_at": 1,
        },
    },
]


@pytest.mark.asyncio
@pytest.mark.parametrize("auth", AUTH_CONFIGS)
async def test_client_adapter_bypasses_configured_auth(kind, auth, auth_provider):
    adapter = MutableAuth()
    config = ClientConfig(api_url="https://processing.test", auth=auth)
    client = kind(config=config, auth=adapter)
    try:
        await invoke(client.login, force=True)
        assert not auth_provider.requests
        assert adapter.calls == 0  # Generic adapters execute only on requests.
        await invoke(client.get_conformance)
        runtime = client._http_client
        adapter.value = "second"
        await invoke(client.get_conformance)
        assert client._http_client is runtime
        assert runtime.auth is adapter
        assert adapter.calls == 2
        assert client.token is None
        assert client.config.to_file_dict() == config.to_file_dict()
        assert client._repr_json_()[0] == config.to_file_dict()
        assert [r.headers["authorization"] for r in auth_provider.requests] == [
            "Bearer first",
            "Bearer second",
        ]
        assert all(r.url.host == "processing.test" for r in auth_provider.requests)
        assert all("x-api-key" not in r.headers for r in auth_provider.requests)
        assert all("x-auth-token" not in r.headers for r in auth_provider.requests)
    finally:
        await invoke(client.close)
    assert runtime.is_closed
    with pytest.raises(RuntimeError, match="closed"):
        await invoke(client.get_conformance, auth=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("auth", AUTH_CONFIGS)
@pytest.mark.parametrize("override", ["none", "adapter", "header"])
async def test_request_overrides_skip_configured_login(
    kind, auth, override, auth_provider
):
    client = kind(api_url="https://processing.test", auth=auth)
    options = {
        "none": {"auth": None},
        "adapter": {"auth": MutableAuth()},
        "header": {"headers": {"aUtHoRiZaTiOn": "Bearer explicit"}},
    }[override]
    expected = {"none": None, "adapter": "Bearer first", "header": "Bearer explicit"}
    try:
        await invoke(client.get_conformance, **options)
        assert len(auth_provider.requests) == 1
        request = auth_provider.requests[0]
        assert request.url.host == "processing.test"
        assert request.headers.get("authorization") == expected[override]
        assert "x-api-key" not in request.headers
        assert "x-auth-token" not in request.headers
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_request_overrides_do_not_replace_client_adapter(kind, auth_provider):
    adapter = MutableAuth()
    other = MutableAuth()
    other.value = "other"
    client = kind(api_url="https://processing.test", auth=adapter)
    try:
        for options in (
            {"auth": None},
            {"auth": other},
            {"headers": {"Authorization": "Bearer header"}},
            {
                "auth": httpx2.USE_CLIENT_DEFAULT,
                "headers": {"Authorization": "Bearer header"},
            },
            {"auth": other, "headers": {"Authorization": "Bearer header"}},
            {"auth": httpx2.USE_CLIENT_DEFAULT},
            {},
        ):
            await invoke(client.get_conformance, **options)
        assert [r.headers.get("authorization") for r in auth_provider.requests] == [
            None,
            "Bearer other",
            "Bearer header",
            "Bearer header",
            "Bearer other",
            "Bearer first",
            "Bearer first",
        ]
        assert adapter.calls == 2
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("oauth", [False, True])
async def test_configured_auth_still_works_after_override(kind, oauth, auth_provider):
    auth = (
        {
            "auth_type": "oauth2",
            "token_url": "https://identity.test/token",
            "client_id": "client",
            "username": "user",
            "password": "pass",
        }
        if oauth
        else {"auth_type": "token", "access_token": "static"}
    )
    client = kind(api_url="https://processing.test", auth=auth)
    try:
        await invoke(client.get_conformance, auth=None)
        runtime = client._http_client
        await invoke(client.get_conformance, auth=httpx2.USE_CLIENT_DEFAULT)
        await invoke(client.get_conformance, auth=None)
        assert client._http_client is runtime
        requests = [
            r for r in auth_provider.requests if r.url.host == "processing.test"
        ]
        assert [r.headers.get("authorization") for r in requests] == [
            None,
            "Bearer access-1" if oauth else "Bearer static",
            None,
        ]
        assert len(auth_provider.grants) == int(oauth)
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_override_does_not_mark_missing_config_credentials_ready(
    kind, auth_provider
):
    client = kind(api_url="https://processing.test", auth={"auth_type": "token"})
    try:
        await invoke(client.get_conformance, auth=None)
        with pytest.raises(LoginRequiredError):
            await invoke(client.get_conformance)
        assert len(auth_provider.requests) == 1
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_adapter_skips_keyring_and_rejects_saving(
    kind, auth_provider, monkeypatch
):
    ClientConfig(auth={"auth_type": "token"}).write()
    unused = Mock(side_effect=AssertionError("Unrelated credentials were accessed"))
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", unused)
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", unused)
    client = kind(auth=MutableAuth())
    await invoke(client.get_conformance)
    runtime = client._http_client
    with pytest.raises(ValueError, match="cannot be saved"):
        await invoke(client.login, save=True)
    await invoke(client.logout)
    unused.assert_not_called()
    assert runtime.is_closed


@pytest.mark.asyncio
async def test_adapter_logout_does_not_revoke_configured_token(
    kind, auth_provider, monkeypatch
):
    unused = Mock(side_effect=AssertionError("Unrelated credentials were deleted"))
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", unused)
    client = kind(
        auth=MutableAuth(),
        config=ClientConfig(
            auth=dict(
                auth_type="oidc",
                issuer_url="https://identity.test/realm",
                client_id="client",
                oauth_token={"access_token": "unused"},
            )
        ),
    )
    await invoke(client.logout)
    assert not auth_provider.requests
    unused.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_failure_and_processing_401_are_not_replayed(kind, auth_provider):
    class FailingAuth(httpx2.Auth):
        def auth_flow(self, request):
            raise ValueError("Auth unavailable")
            yield request

    client = kind(auth=FailingAuth())
    try:
        with pytest.raises(ValueError, match="Auth unavailable"):
            await invoke(client.get_conformance)
        assert not auth_provider.requests
    finally:
        await invoke(client.close)
    adapter = MutableAuth()
    client = kind(auth=adapter)
    auth_provider.statuses.append(401)
    try:
        with pytest.raises(ClientError):
            await invoke(client.get_conformance)
        assert len(auth_provider.requests) == adapter.calls == 1
    finally:
        await invoke(client.close)


def test_auth_rejects_unsupported_object(kind):
    with pytest.raises(TypeError, match="httpx2.Auth"):
        kind(auth=object())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options, expected_header, expected_value",
    [
        ({}, "X-Auth-Token", "original"),
        ({"auth": None}, "X-Auth-Token", "original"),
        ({"auth": {"access_token": "partial"}}, "X-Auth-Token", "partial"),
        (
            {"auth": {"auth_type": "token", "access_token": "replacement"}},
            "Authorization",
            "Bearer replacement",
        ),
        (
            {"auth": TokenAuthConfig(access_token="model-token")},  # noqa: S106 - test credential
            "Authorization",
            "Bearer model-token",
        ),
        ({"auth": {"auth_type": "none"}}, None, None),
    ],
)
async def test_constructor_auth_retains_configuration_resolution(
    kind, auth_provider, options, expected_header, expected_value
):
    config = ClientConfig(
        api_url="https://processing.test",
        auth={
            "auth_type": "token",
            "access_token": "original",
            "access_token_header": "X-Auth-Token",
        },
    )
    client = kind(config=config, **options)
    try:
        await invoke(client.get_conformance)
        headers = auth_provider.requests[-1].headers
        if expected_header:
            assert headers[expected_header] == expected_value
        else:
            assert "authorization" not in headers
            assert "x-auth-token" not in headers
        assert config.auth.access_token == "original"  # noqa: S105 - test credential
        assert config.auth.access_token_header == "X-Auth-Token"  # noqa: S105 - header name
    finally:
        await invoke(client.close)
