# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

# All credentials, token values, and endpoint URLs below are fake fixtures.
# ruff: noqa: S105, S106

"""Throwaway Authlib lifecycle proof; no Cuiman imports or real HTTP/keyring I/O.

Run with: pixi run --manifest-path tools/authlib_proof/pixi.toml proof
Only persist_token below represents proposed application policy. Everything else
is an executable experiment using fake credentials and assertion-based checks.
"""

import asyncio
import inspect
import json
import warnings
from collections.abc import Callable, Mapping
from importlib.metadata import version
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx2
from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuth2Client
from authlib.oauth2.rfc6749 import wrappers

TOKEN_URL = "https://identity.example.test/token"
"""Mock token endpoint; the transport never opens a network connection."""
API_URL = "https://api.example.test/processes"
"""Mock protected resource used for both requests on the same client."""


class StorageUnavailable(RuntimeError):
    """Simulated credential-store failure, not a provider authentication error."""


class CredentialStorageWarning(UserWarning):
    """Live authentication works, but its persistence could not be confirmed."""


def persist_token(
    token: Mapping[str, Any],
    save: Callable[[dict[str, Any]], None],
    *,
    required: bool = False,
) -> None:
    """Save a token snapshot; explicit saving requires success, API use does not."""
    try:
        save(dict(token))
    except StorageUnavailable:
        if required:
            raise
        warnings.warn(
            "Credentials are active, but saving could not be confirmed. "
            "Restarting may require login.",
            CredentialStorageWarning,
            stacklevel=2,
        )


class FakeStore:
    """Store complete JSON snapshots in memory and inject a recoverable outage."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.fail = False
        self.saved: dict[str, Any] | None = None

    def save(self, token: dict[str, Any]) -> None:
        """Simulate storage serialization, without sharing the live token object."""
        if self.fail:
            self.events.append("save unavailable")
            raise StorageUnavailable("Mock store unavailable")
        self.saved = json.loads(json.dumps(token))
        self.events.append(f"saved {token['access_token']}")


class FakeProvider:
    """Validate OAuth wire requests and issue deterministic fake token responses."""

    def __init__(self, grant: str, omit_refresh: bool, events: list[str]) -> None:
        self.grant = grant
        self.omit_refresh = omit_refresh
        self.events = events
        self.generation = 0
        self.resource_tokens: list[str] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        """Handle exactly two grants and two protected requests; reject other URLs."""
        if str(request.url) == TOKEN_URL:
            assert request.method == "POST"
            assert "authorization" not in request.headers
            data = parse_qs(request.content.decode())
            expected = {
                "client_id": ["proof-client"],
                "client_secret": ["proof-secret"],
            }
            if self.generation and self.grant == "password":
                expected.update(
                    grant_type=["refresh_token"], refresh_token=["refresh-1"]
                )
            else:
                expected["grant_type"] = [self.grant]
                if self.grant == "password":
                    expected.update(
                        username=["proof-user"], password=["proof-password"]
                    )
            assert data == expected
            self.generation += 1
            assert self.generation <= 2
            token = {
                "access_token": f"access-{self.generation}",
                "token_type": "Bearer",
                "expires_in": 120,
                "scope": "processes:read",
            }
            if self.grant == "password" and not (
                self.generation == 2 and self.omit_refresh
            ):
                token["refresh_token"] = f"refresh-{self.generation}"
            self.events.append(
                f"{data['grant_type'][0]} issued {token['access_token']}"
            )
            return httpx2.Response(200, json=token)

        assert str(request.url) == API_URL
        assert request.method == "GET"
        signed_token = request.headers["authorization"]
        assert signed_token == f"Bearer access-{self.generation}"
        self.resource_tokens.append(signed_token)
        self.events.append(f"API accepted access-{self.generation}")
        return httpx2.Response(200, json={"processes": []})


async def invoke(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Let the experiment drive matching sync/async operations with one scenario."""
    result = function(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


async def run_case(
    *, asynchronous: bool, grant: str, storage_failure: bool, omit_refresh: bool = False
) -> None:
    """Prove acquisition, expiry, persistence ordering, restore, and close behavior."""
    events: list[str] = []
    store = FakeStore(events)
    provider = FakeProvider(grant, omit_refresh, events)
    callbacks: list[dict[str, str]] = []

    def on_update(token: Mapping[str, Any], **previous: str) -> None:
        assert token is client.token  # Authlib publishes before invoking us.
        assert token["access_token"] == "access-2"
        callbacks.append(previous)
        events.append("callback sees live access-2")
        persist_token(token, store.save)

    async def on_update_async(token: Mapping[str, Any], **previous: str) -> None:
        on_update(token, **previous)

    async def handle_async(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(0)  # Exercise the awaitable transport path.
        return provider.handle(request)

    client_type = AsyncOAuth2Client if asynchronous else OAuth2Client
    client = client_type(
        client_id="proof-client",
        client_secret="proof-secret",
        token_endpoint_auth_method="client_secret_post",
        token_endpoint=TOKEN_URL,
        grant_type=grant,
        update_token=on_update_async if asynchronous else on_update,
        transport=httpx2.MockTransport(
            handle_async if asynchronous else provider.handle
        ),
        trust_env=False,
        leeway=0,
    )
    assert isinstance(client, httpx2.AsyncClient if asynchronous else httpx2.Client)
    clock = SimpleNamespace(now=1_800_000_000)
    try:
        # Patch only Authlib's clock reference; never mutate client.token to expire it.
        with patch.object(wrappers, "time", SimpleNamespace(time=lambda: clock.now)):
            credentials = (
                {"username": "proof-user", "password": "proof-password"}
                if grant == "password"
                else {}
            )
            token = await invoke(client.fetch_token, TOKEN_URL, **credentials)
            assert token is client.token
            assert callbacks == []  # fetch_token does not call update_token.
            assert store.saved is None
            assert token["expires_at"] == clock.now + 120
            persist_token(token, store.save, required=True)
            response = await invoke(client.get, API_URL)
            assert response.status_code == 200
            assert provider.generation == 1

            clock.now += 121
            events.append("clock advanced past expiry")
            store.fail = storage_failure
            with warnings.catch_warnings(record=True) as reported:
                warnings.simplefilter("always", CredentialStorageWarning)
                response = await invoke(client.get, API_URL)
            assert response.status_code == 200
            assert [item.category for item in reported] == (
                [CredentialStorageWarning] if storage_failure else []
            )
            assert provider.resource_tokens == ["Bearer access-1", "Bearer access-2"]
            assert callbacks == [
                {"refresh_token": "refresh-1"}
                if grant == "password"
                else {"access_token": "access-1"}
            ]
            assert client.token["expires_at"] == clock.now + 120
            assert client.token["scope"] == "processes:read"
            assert client.token["token_type"] == "Bearer"
            if grant == "password":
                assert client.token["refresh_token"] == (
                    "refresh-1" if omit_refresh else "refresh-2"
                )
            else:
                assert "refresh_token" not in client.token
            assert store.saved is not None
            assert store.saved["access_token"] == (
                "access-1" if storage_failure else "access-2"
            )

            if storage_failure:
                active = dict(client.token)
                try:
                    persist_token(client.token, store.save, required=True)
                except StorageUnavailable:
                    events.append("explicit save reported failure")
                else:
                    raise AssertionError("An explicit save must report storage failure")
                assert client.token == active
                store.fail = False
                persist_token(client.token, store.save, required=True)
                events.append("explicit save recovered without a provider exchange")

            assert store.saved == dict(client.token)
            assert provider.generation == 2
            # A later load retains absolute expiry instead of renewing expires_in.
            clock.now += 30
            restored = wrappers.OAuth2Token(json.loads(json.dumps(store.saved)))
            assert restored == client.token
            assert restored.is_expired(leeway=0) is False
            clock.now = restored["expires_at"] + 1
            assert restored.is_expired(leeway=0) is True
    finally:
        await invoke(client.aclose if asynchronous else client.close)
    assert client.is_closed
    mode = "async" if asynchronous else "sync"
    scenario = "store outage" if storage_failure else "store available"
    if omit_refresh:
        scenario += ", omitted refresh token"
    print(f"PASS {mode} / {grant} / {scenario}")
    print("  " + " -> ".join(events))
    print("  saved fake token: " + json.dumps(store.saved, sort_keys=True))


async def main() -> None:
    """Run the bounded proof against pinned dependencies, with fake data only."""
    assert version("authlib") == "1.8.0"
    assert version("httpx2") == "2.5.0"
    print(f"Authlib {version('authlib')}; HTTPX2 {version('httpx2')}")
    for asynchronous in (False, True):
        for grant in ("password", "client_credentials"):
            for storage_failure in (False, True):
                await run_case(
                    asynchronous=asynchronous,
                    grant=grant,
                    storage_failure=storage_failure,
                )
        await run_case(
            asynchronous=asynchronous,
            grant="password",
            storage_failure=False,
            omit_refresh=True,
        )
    print("10 scenarios passed; all clients closed; no network or keyring used.")


if __name__ == "__main__":
    asyncio.run(main())
