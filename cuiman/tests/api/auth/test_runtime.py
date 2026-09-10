"""Shared lifecycle exercised through real sync/async clients and mock HTTP."""

import asyncio
import inspect
import json
from unittest.mock import Mock

import pytest
from authlib.integrations.base_client.errors import InvalidTokenError, OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuth2Client
from pydantic import ValidationError

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import LoginRequiredError, OAuth2AuthConfig, OidcAuthConfig
from cuiman.api.auth.oauth2_client import CredentialStorageWarning
from cuiman.api.auth.secret_store import SecretStoreError
from cuiman.api.exceptions import ClientError


async def invoke(method, *args, **kwargs):
    result = method(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


@pytest.fixture(params=[Client, AsyncClient], ids=["sync", "async"])
def kind(request):
    return request.param


def oauth(**changes):
    return dict(
        auth_type="oauth2",
        token_url="https://identity.test/token",
        client_id="client",
        username="user",
        password="secret",
        **changes,
    )


def oidc(**changes):
    return dict(
        auth_type="oidc",
        issuer_url="https://identity.test/realm",
        client_id="client",
        **changes,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("grant", ["password", "client_credentials"])
async def test_direct_authlib_client_acquires_reuses_refreshes_and_closes(
    kind, grant, auth_provider
):
    client = kind(
        api_url="https://processing.test",
        auth=oauth(grant_type=grant, client_secret="secret"),
    )
    assert client.token is None
    await invoke(client.get_conformance)
    runtime = client._http_client
    assert type(runtime) is (AsyncOAuth2Client if kind is AsyncClient else OAuth2Client)
    assert auth_provider.grants[0]["grant_type"] == [grant]
    await invoke(client.get_conformance)
    assert len(auth_provider.grants) == 1
    snapshot = client.token
    snapshot["extra"]["kept"] = False
    assert client.token["extra"]["kept"] is True
    assert client.config.auth.oauth_token is None
    auth_provider.now += 601
    await invoke(client.get_conformance)
    assert auth_provider.grants[-1]["grant_type"] == [
        "refresh_token" if grant == "password" else grant
    ]
    assert auth_provider.requests[-1].headers["Authorization"] == "Bearer access-2"
    assert client._http_client is runtime
    await invoke(client.close)
    await invoke(client.close)
    assert runtime.is_closed
    with pytest.raises(RuntimeError, match="closed"):
        await invoke(client.get_conformance)


@pytest.mark.asyncio
async def test_refresh_retains_an_omitted_refresh_token(kind, auth_provider):
    client = kind(
        api_url="https://processing.test",
        auth=oauth(
            oauth_token=dict(access_token="old", refresh_token="refresh", expires_at=1)
        ),
    )
    auth_provider.replies.append((200, dict(access_token="new", expires_in=600)))
    await invoke(client.get_conformance)
    assert client.token["refresh_token"] == "refresh"
    await invoke(client.close)


@pytest.mark.asyncio
async def test_resource_401_is_never_replayed(kind, auth_provider):
    client = kind(api_url="https://processing.test", auth=oauth())
    auth_provider.statuses.append(401)
    with pytest.raises(ClientError):
        await invoke(client.get_conformance)
    assert len(auth_provider.grants) == 1
    assert (
        len([r for r in auth_provider.requests if r.url.host == "processing.test"]) == 1
    )
    await invoke(client.close)


@pytest.mark.asyncio
async def test_rejected_refresh_does_not_fall_back_to_password(kind, auth_provider):
    client = kind(
        api_url="https://processing.test",
        auth=oauth(
            oauth_token=dict(access_token="old", refresh_token="bad", expires_at=1)
        ),
    )
    auth_provider.replies.append((400, {"error": "invalid_grant"}))
    with pytest.raises(OAuthError):
        await invoke(client.get_conformance)
    assert [g["grant_type"] for g in auth_provider.grants] == [["refresh_token"]]
    await invoke(client.close)


@pytest.mark.asyncio
async def test_expired_password_token_without_refresh_requires_explicit_login(
    kind, auth_provider
):
    client = kind(
        api_url="https://processing.test",
        auth=oauth(oauth_token=dict(access_token="old", expires_at=1)),
    )
    with pytest.raises(InvalidTokenError):
        await invoke(client.get_conformance)
    assert not auth_provider.grants
    await invoke(client.login, force=True, interactive=False)
    assert client.token["access_token"] == "access-1"
    await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth,header,value",
    [
        ({"auth_type": "none"}, None, None),
        (
            {"auth_type": "basic", "username": "user", "password": "pass"},
            "Authorization",
            "Basic dXNlcjpwYXNz",
        ),
        (
            {"auth_type": "token", "access_token": "static"},
            "Authorization",
            "Bearer static",
        ),
        (
            {"auth_type": "token", "access_token": "static", "use_bearer": False},
            "X-Auth-Token",
            "static",
        ),
        ({"auth_type": "api-key", "api_key": "key"}, "X-API-Key", "key"),
        (
            {
                "auth_type": "login",
                "login_url": "https://identity.test/login",
                "username": "u",
                "password": "p",
            },
            "Authorization",
            "Bearer proprietary",
        ),
    ],
)
async def test_every_non_oauth_mechanism_uses_one_owned_http_client(
    kind, auth, header, value, auth_provider
):
    client = kind(api_url="https://processing.test", auth=auth)
    await invoke(client.get_conformance)
    runtime = client._http_client
    await invoke(client.get_conformance)
    assert client._http_client is runtime
    if header:
        assert auth_provider.requests[-1].headers[header] == value
    assert len([r for r in auth_provider.requests if r.url.path == "/login"]) <= 1
    assert client.token is None
    await invoke(client.close)
    assert runtime.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth",
    [
        dict(auth_type="token"),
        dict(auth_type="basic"),
        dict(auth_type="api-key"),
        dict(
            auth_type="oauth2",
            token_url="https://identity.test/token",
            client_id="client",
        ),
        oidc(),
    ],
)
async def test_missing_credentials_never_start_interaction(
    kind, auth, auth_provider, monkeypatch
):
    prompt = Mock(side_effect=AssertionError("unexpected prompt"))
    monkeypatch.setattr("cuiman.api.client_mixin_base.prompt_auth", prompt)
    client = kind(api_url="https://processing.test", auth=auth)
    with pytest.raises(LoginRequiredError):
        await invoke(client.get_conformance)
    prompt.assert_not_called()
    assert not auth_provider.grants
    await invoke(client.close)


@pytest.mark.asyncio
async def test_signed_oidc_login_refresh_and_logout(kind, auth_provider, monkeypatch):
    delete = Mock()
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", delete)
    client = kind(api_url="https://processing.test", auth=oidc())
    await invoke(client.login)
    assert auth_provider.grants[0]["grant_type"] == ["authorization_code"]
    assert auth_provider.grants[0]["code_verifier"]
    auth_provider.now += 601
    await invoke(client.get_conformance)
    assert client.token["refresh_token"] == "refresh-2"
    assert auth_provider.grants[-1]["grant_type"] == ["refresh_token"]
    runtime = client._http_client
    await invoke(client.logout)
    delete.assert_called_once()
    assert runtime.is_closed
    assert client.token is None
    assert auth_provider.requests[-1].url.path == "/revoke"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://other.test"},
        {"aud": "other", "azp": "client"},
        {"nonce": "wrong"},
        {"exp": 1},
        {"iat": 9999999999},
    ],
)
async def test_oidc_rejects_invalid_claims_before_signing_or_saving(
    kind, claims, auth_provider
):
    client = kind(api_url="https://processing.test", auth=oidc())
    saved = Mock()
    client.config.auth.set_secret_persistor(saved)
    auth_provider.claims = claims
    with pytest.raises(Exception):
        await invoke(client.login)
    assert client.token is None
    saved.assert_not_called()
    assert not [r for r in auth_provider.requests if r.url.host == "processing.test"]
    await invoke(client.close)


@pytest.mark.asyncio
async def test_oidc_requires_initial_id_token(kind, auth_provider):
    auth_provider.include_id = False
    client = kind(api_url="https://processing.test", auth=oidc())
    with pytest.raises(ValueError, match="ID token"):
        await invoke(client.login)
    assert client.token is None
    await invoke(client.close)


@pytest.mark.asyncio
async def test_optional_save_failure_retains_live_token_but_explicit_save_raises(
    kind, auth_provider, monkeypatch
):
    client = kind(api_url="https://processing.test", auth=oauth())
    client.config.auth.set_secret_persistor(
        Mock(side_effect=SecretStoreError("unavailable"))
    )
    with pytest.warns(CredentialStorageWarning):
        await invoke(client.login, interactive=False)
    assert client.token["access_token"] == "access-1"
    monkeypatch.setattr(
        "cuiman.api.auth.oauth2_client.save_auth_secrets",
        Mock(side_effect=SecretStoreError("unavailable")),
    )
    with pytest.raises(SecretStoreError):
        await invoke(client.login, save=True)
    await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("loader", [ClientConfig.create, ClientConfig.from_file])
async def test_wrapped_configuration_keeps_profile_for_save_and_logout(
    kind, loader, auth_provider, monkeypatch, tmp_path
):
    path = tmp_path / "named"
    ClientConfig(api_url="https://processing.test", auth=oauth()).write(path)
    monkeypatch.setattr(
        "cuiman.api.config.load_auth_secrets",
        lambda *args: {"username": "user", "password": "secret"},
    )
    saved, deleted = Mock(), Mock()
    monkeypatch.setattr("cuiman.api.auth.oauth2_client.save_auth_secrets", saved)
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", deleted)
    config = loader(config_path=path)
    assert "_source_path" not in config.model_dump()
    client = kind(config=config)
    await invoke(client.login, interactive=False, save=True)
    assert saved.call_args.args[:3] == (path, "https://processing.test/", "oauth2")
    await invoke(client.logout)
    deleted.assert_called_once_with(path, "https://processing.test/")


@pytest.mark.asyncio
async def test_forced_login_uses_changed_client_secret(kind, auth_provider):
    client = kind(api_url="https://processing.test", auth=oauth())
    await invoke(client.login, interactive=False)
    runtime = client._http_client
    assert "client_secret" not in auth_provider.grants[-1]
    client.config.auth.client_secret = "changed"
    await invoke(client.login, force=True, interactive=False)
    assert client._http_client is runtime
    assert auth_provider.grants[-1]["client_secret"] == ["changed"]
    client.config.auth.client_secret = None
    await invoke(client.login, force=True, interactive=False)
    assert "client_secret" not in auth_provider.grants[-1]
    await invoke(client.close)


@pytest.mark.asyncio
async def test_refresh_persists_complete_token_to_original_store(
    kind, auth_provider, monkeypatch, tmp_path
):
    path = tmp_path / "saved"
    ClientConfig(
        api_url="https://processing.test",
        auth=OAuth2AuthConfig(
            token_url="https://identity.test/token", client_id="client"
        ),
    ).write(path)
    monkeypatch.setattr(
        "cuiman.api.config.load_auth_secrets",
        lambda *a: {
            "oauth_token": json.dumps(
                dict(access_token="old", refresh_token="old-refresh", expires_at=1)
            )
        },
    )
    saved = Mock()
    monkeypatch.setattr("cuiman.api.config.save_auth_secrets", saved)
    client = kind(config_path=str(path))
    await invoke(client.get_conformance)
    args = saved.call_args.args
    assert args[:3] == (path, "https://processing.test/", "oauth2")
    token = json.loads(args[3]["oauth_token"])
    assert token == client.token
    assert "access_token" not in args[3]
    await invoke(client.close)


@pytest.mark.parametrize(
    "config",
    [
        OAuth2AuthConfig(token_url="https://identity.test/token", client_id="client"),
        OidcAuthConfig(issuer_url="https://identity.test/realm", client_id="client"),
    ],
)
def test_clean_token_schema_and_secret_serialization(config):
    for field in ("access_token", "refresh_token", "use_bearer", "access_token_header"):
        with pytest.raises(ValidationError):
            type(config)(**config.to_public_dict(), **{field: "obsolete"})
    config.oauth_token = dict(
        access_token="secret", refresh_token="refresh", expires_at=1800000000
    )
    assert "oauth_token" not in config.to_public_dict()
    assert json.loads(config.to_secret_dict()["oauth_token"]) == config.oauth_token


def test_explicit_token_snapshot_bypasses_saved_keyring_credentials(monkeypatch):
    ClientConfig(api_url="https://processing.test").write()
    loaded = Mock(side_effect=AssertionError("must not read unrelated credentials"))
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", loaded)
    token = {"access_token": "explicit", "expires_at": 1900000000}
    config = ClientConfig.create(auth=oauth(oauth_token=token))
    assert config.auth.oauth_token == token
    loaded.assert_not_called()


@pytest.mark.asyncio
async def test_static_save_and_per_request_authorization_override(
    kind, auth_provider, monkeypatch
):
    save = Mock()
    monkeypatch.setattr("cuiman.api.auth.oauth2_client.save_auth_secrets", save)
    client = kind(
        api_url="https://processing.test",
        auth={"auth_type": "token", "access_token": "static"},
    )
    await invoke(client.login, interactive=False)
    await invoke(client.login, save=True)
    save.assert_called_once()
    await invoke(client.close)
    client = kind(api_url="https://processing.test", auth=oauth())
    await invoke(client.get_conformance, headers={"authorization": "Bearer explicit"})
    assert auth_provider.requests[-1].headers["authorization"] == "Bearer explicit"
    await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke", [False, True])
async def test_logout_bootstrap_cleans_up_even_if_revocation_fails(
    kind, revoke, auth_provider, monkeypatch
):
    if not revoke:
        del auth_provider.metadata["revocation_endpoint"]
    auth_provider.revoke_status = 503
    deleted = Mock()
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", deleted)
    client = kind(
        api_url="https://processing.test",
        auth=oidc(oauth_token={"access_token": "old"}),
    )
    if revoke:
        import httpx2

        with pytest.raises(httpx2.HTTPStatusError):
            await invoke(client.logout)
    else:
        await invoke(client.logout)
    deleted.assert_called_once()
    assert client.config.auth.oauth_token is None
    assert client._closed
    assert client._http_client is None


@pytest.mark.asyncio
async def test_cancelled_async_oidc_wait_stops_worker_and_allows_retry(
    auth_provider, monkeypatch
):
    import threading

    import cuiman.api.async_client_mixin as mixin

    original = mixin.authorize
    started, stopped = threading.Event(), threading.Event()

    def wait(*args, cancelled, **kwargs):
        started.set()
        assert cancelled.wait(3)
        stopped.set()
        raise asyncio.CancelledError()

    monkeypatch.setattr(mixin, "authorize", wait)
    client = AsyncClient(api_url="https://processing.test", auth=oidc())
    task = asyncio.create_task(client.login())
    assert await asyncio.to_thread(started.wait, 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await asyncio.to_thread(stopped.wait, 3)
    assert client.token is None
    assert not auth_provider.grants
    monkeypatch.setattr(mixin, "authorize", original)
    await client.login()
    await client.close()


@pytest.mark.asyncio
async def test_cancelled_credential_prompt_cannot_publish_late_credentials(monkeypatch):
    import threading

    from cuiman.api.auth import TokenAuthConfig

    started, release, stopped = threading.Event(), threading.Event(), threading.Event()

    def prompt(auth):
        started.set()
        assert release.wait(3)
        stopped.set()
        return TokenAuthConfig(access_token="late")

    monkeypatch.setattr("cuiman.api.client_mixin_base.prompt_auth", prompt)
    client = AsyncClient(api_url="https://processing.test", auth={"auth_type": "token"})
    task = asyncio.create_task(client.login())
    assert await asyncio.to_thread(started.wait, 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    assert await asyncio.to_thread(stopped.wait, 3)
    assert client.config.auth.access_token is None
    assert client._http_client is None
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["matching", "omitted", "wrong", "signature", "algorithm"]
)
async def test_oidc_refresh_validation_after_restart(kind, mode, auth_provider):
    import time

    from joserfc import jwt
    from joserfc.errors import JoseError
    from joserfc.jwk import OctKey, RSAKey

    client = kind(api_url="https://processing.test", auth=oidc())
    await invoke(client.login)
    snapshot = client.token
    await invoke(client.close)
    client = kind(api_url="https://processing.test", auth=oidc(oauth_token=snapshot))
    claims = dict(
        iss="https://identity.test/realm",
        sub="user",
        aud="client",
        iat=int(time.time()),
        exp=int(time.time()) + 600,
    )
    if mode != "omitted":
        claims["nonce"] = "wrong" if mode == "wrong" else auth_provider.nonce
    key = RSAKey.generate_key(2048) if mode == "signature" else auth_provider.key
    if mode == "algorithm":
        key = OctKey.generate_key(256)
    id_token = jwt.encode(
        {"alg": "HS256" if mode == "algorithm" else "RS256"}, claims, key
    )
    auth_provider.replies.append(
        (200, dict(access_token="renewed", id_token=id_token, expires_in=600))
    )
    auth_provider.now += 601
    if mode in ("wrong", "signature", "algorithm"):
        with pytest.raises(JoseError):
            await invoke(client.get_conformance)
        assert client.token is None
    else:
        await invoke(client.get_conformance)
        assert client.token["_cuiman_nonce"] == auth_provider.nonce
        assert client.token["refresh_token"] == snapshot["refresh_token"]
    await invoke(client.close)
