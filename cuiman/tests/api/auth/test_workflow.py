"""Configure, sign in, share an app session, rotate credentials, and log out."""

import asyncio
import json
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from joserfc.jwk import RSAKey
from typer.testing import CliRunner

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import LoginRequiredError
from cuiman.api.auth.secret_store import load_auth_secrets, save_auth_secrets
from cuiman.app import App
from cuiman.app.launch import (
    LAUNCH_ENDPOINT,
    SERVICE_PROXY_ENDPOINT,
    LaunchedAppService,
)
from cuiman.cli.cli import cli


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [Client, AsyncClient])
@pytest.mark.parametrize("flow", ["password", "client_credentials", "oidc"])
async def test_configure_to_api_and_app_rotation_then_logout(
    kind, flow, auth_provider, monkeypatch, tmp_path
):
    records = {}
    monkeypatch.setattr(
        "keyring.get_password", lambda service, account: records.get((service, account))
    )
    monkeypatch.setattr(
        "keyring.set_password",
        lambda service, account, value: records.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        "keyring.delete_password",
        lambda service, account: records.pop((service, account), None),
    )
    monkeypatch.setattr(
        "typer.prompt", Mock(side_effect=AssertionError("Unexpected credential prompt"))
    )
    path = tmp_path / "selected.yaml"
    url = "https://processing.test/"
    runner = CliRunner()
    options = [
        "configure",
        "--config",
        str(path),
        "--api-url",
        url,
        "--client-id",
        "client",
    ]
    if flow == "oidc":
        options += [
            "--auth-type",
            "oidc",
            "--issuer-url",
            "https://identity.test/realm",
            "--scope",
            "profile",
        ]
    else:
        options += [
            "--auth-type",
            "oauth2",
            "--token-url",
            "https://identity.test/token",
            "--grant-type",
            flow,
        ]
        if flow == "password":
            monkeypatch.setenv("EOZILLA_AUTH__USERNAME", "user")
            monkeypatch.setenv("EOZILLA_AUTH__PASSWORD", "password")
        else:
            monkeypatch.setenv("EOZILLA_AUTH__CLIENT_SECRET", "client-secret")
    configured = runner.invoke(cli, options)
    assert configured.exit_code == 0, configured.output
    logged_in = runner.invoke(cli, ["login", "--config", str(path), "--no-browser"])
    assert logged_in.exit_code == 0, logged_in.output
    for variable in ("USERNAME", "PASSWORD", "CLIENT_SECRET"):
        monkeypatch.delenv("EOZILLA_AUTH__" + variable, raising=False)
    assert len(auth_provider.grants) == 1
    assert not any(
        secret in path.read_text()
        for secret in ("access_token", "refresh_token", "password:", "client_secret")
    )

    unrelated = [(tmp_path / "other.yaml", url), (path, "https://other-service.test/")]
    for other_path, other_url in unrelated:
        save_auth_secrets(other_path, other_url, "token", {"access_token": "unrelated"})
    owner = kind(config=ClientConfig.create(config_path=path))

    async def call(method):
        operation = getattr(owner, method)
        return (
            await operation()
            if kind is AsyncClient
            else await asyncio.to_thread(operation)
        )

    try:
        await call("get_conformance")
        runtime = owner._http_client
        service = LaunchedAppService(
            App.create_remote_store(), owner.config, **owner._app_callbacks()
        )
        app = FastAPI()
        service._init_app(app)
        with TestClient(app) as browser:
            response = await asyncio.to_thread(
                browser.post,
                LAUNCH_ENDPOINT,
                json={"launch": service.create_launch_code()},
            )
            assert response.status_code == 204
            assert len(auth_provider.grants) == 1
            auth_provider.now += 601
            if flow == "oidc":
                auth_provider.refresh_id = True
                auth_provider.key = RSAKey.generate_key(2048)
            response = await asyncio.to_thread(
                browser.get, SERVICE_PROXY_ENDPOINT + "/conformance"
            )
            assert response.status_code == 200
            assert "access-" not in response.text
            assert len(auth_provider.grants) == 2
            if flow != "client_credentials":
                assert auth_provider.grants[-1]["refresh_token"] == ["refresh-1"]
                assert owner.token["refresh_token"] == "refresh-2"
            if flow == "oidc":
                assert (
                    len([r for r in auth_provider.requests if r.url.path == "/keys"])
                    == 2
                )
            stored = load_auth_secrets(path, url, owner.config.auth.auth_type)
            assert json.loads(stored["oauth_token"]) == owner.token
            assert owner._http_client is runtime
            await call("get_conformance")
            assert len(auth_provider.grants) == 2
            await call("logout")
            assert runtime.is_closed
            assert owner.token is None
            response = await asyncio.to_thread(
                browser.get, SERVICE_PROXY_ENDPOINT + "/conformance"
            )
            assert response.status_code == 502
            assert "access-" not in response.text
        assert load_auth_secrets(path, url, owner.config.auth.auth_type) == {}
        for other_path, other_url in unrelated:
            assert load_auth_secrets(other_path, other_url, "token") == {
                "access_token": "unrelated"
            }
        if flow == "oidc":
            assert (
                len([r for r in auth_provider.requests if r.url.path == "/revoke"]) == 1
            )
        owner = kind(config_path=str(path))
        with pytest.raises(LoginRequiredError):
            await call("get_conformance")
    finally:
        await call("close")
