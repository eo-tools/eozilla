"""Local interaction and callback rejection, leaving protocol checks to Authlib."""

import asyncio
import threading
from unittest.mock import Mock

import pytest
from authlib.oauth2.rfc6749.errors import OAuth2Error

from cuiman.api.auth.config import (
    ApiKeyAuthConfig,
    BasicAuthConfig,
    NoAuthConfig,
    OAuth2AuthConfig,
    TokenAuthConfig,
)
from cuiman.api.auth.interactive import _wait_for_callback, authorize, prompt_auth


@pytest.mark.parametrize(
    "auth,answers,expected",
    [
        (BasicAuthConfig(), ["user", "pass"], {"username": "user", "password": "pass"}),
        (
            OAuth2AuthConfig(
                token_url="https://identity.test/token",
                client_id="client",
                client_secret="secret",
            ),
            ["user", "pass"],
            {"username": "user", "password": "pass", "client_secret": "secret"},
        ),
        (
            OAuth2AuthConfig(
                token_url="https://identity.test/token",
                client_id="client",
                grant_type="client_credentials",
            ),
            ["secret"],
            {"client_secret": "secret"},
        ),
        (TokenAuthConfig(), ["token"], {"access_token": "token"}),
        (ApiKeyAuthConfig(), ["key"], {"api_key": "key"}),
        (NoAuthConfig(), [], {}),
    ],
)
def test_prompts_collect_secrets_without_publishing_them(
    auth, answers, expected, monkeypatch
):
    prompt = Mock(side_effect=answers)
    monkeypatch.setattr("typer.prompt", prompt)
    before = auth.model_dump()
    assert prompt_auth(auth).to_secret_dict() == expected
    assert auth.model_dump() == before
    for call in prompt.call_args_list:
        if call.args[0] != "Username":
            assert call.kwargs["hide_input"]


@pytest.mark.parametrize(
    "parameters",
    [
        {"state": ["wrong"], "code": ["code"]},
        {"code": ["code"]},
        {"state": ["state"]},
        {"state": ["state"], "error": ["access_denied"]},
        {"state": ["state", "state"], "code": ["code"]},
        {"state": ["state"], "code": ["code", "code"]},
        {"state": ["state"], "error": ["a", "b"]},
        {"state": ["state"], "error_description": ["a", "b"]},
    ],
)
def test_callback_rejection(parameters, monkeypatch):
    monkeypatch.setattr("webbrowser.open", lambda url: True)
    server = Mock(redirect_uri="http://127.0.0.1:1234/callback")
    server.wait_for_callback.return_value = parameters
    with pytest.raises((ValueError, OAuth2Error)):
        authorize(server, "https://identity.test/authorize", "state", no_browser=False)


def test_headless_callback_and_browser_failure(monkeypatch, capsys):
    server = Mock(redirect_uri="http://127.0.0.1:1234/callback")
    server.wait_for_callback.return_value = {"code": ["code"], "state": ["state"]}
    assert (
        authorize(server, "https://identity.test/authorize", "state", no_browser=True)
        == "code"
    )
    assert "https://identity.test/authorize" in capsys.readouterr().out
    monkeypatch.setattr("webbrowser.open", lambda url: False)
    with pytest.raises(ValueError, match="no_browser"):
        authorize(server, "https://identity.test/authorize", "state", no_browser=False)


def test_callback_wait_cancellation_retry_and_timeout(monkeypatch):
    server = Mock()
    server.wait_for_callback.side_effect = [TimeoutError(), {"code": ["code"]}]
    event = threading.Event()
    assert _wait_for_callback(server, event) == {"code": ["code"]}
    event.set()
    with pytest.raises(asyncio.CancelledError):
        _wait_for_callback(server, event)
    event.clear()
    monkeypatch.setattr(
        "cuiman.api.auth.interactive.time.monotonic", Mock(side_effect=[0, 301])
    )
    with pytest.raises(TimeoutError):
        _wait_for_callback(server, event)


@pytest.mark.parametrize("force", [False, True])
def test_partial_credentials_prompt_only_for_missing_values(force, monkeypatch):
    auth = BasicAuthConfig(username="existing")
    prompt = Mock(side_effect=["replacement", "password"] if force else ["password"])
    monkeypatch.setattr("typer.prompt", prompt)
    candidate = prompt_auth(auth, force=force)
    assert candidate.username == ("replacement" if force else "existing")
    assert candidate.password == "password"
    assert auth.password is None
    assert [call.args[0] for call in prompt.call_args_list] == (
        ["Username", "Password"] if force else ["Password"]
    )
    assert prompt.call_args.kwargs["default"] is None


def test_config_validation_errors_do_not_echo_secret_inputs():
    from cuiman import ClientConfig
    from pydantic import ValidationError

    for make in (
        BasicAuthConfig,
        lambda **kwargs: ClientConfig(auth={"auth_type": "basic", **kwargs}),
    ):
        with pytest.raises(ValidationError) as error:
            make(username="user", password={"secret": "DO-NOT-ECHO"})
        assert "DO-NOT-ECHO" not in str(error.value)


def test_static_tokens_reject_removed_bearer_switch():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TokenAuthConfig(use_bearer=True)
    with pytest.raises(ValidationError):
        TokenAuthConfig(access_token_header="")
