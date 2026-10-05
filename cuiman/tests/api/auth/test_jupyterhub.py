"""JupyterHub token retrieval through native HTTPX2 and both Cuiman clients."""

import inspect
import json

import httpx2
import pytest

from cuiman import AsyncClient, Client
from cuiman.api.auth import JupyterHubAuth, JupyterHubAuthError
from cuiman.api.exceptions import ClientError
from cuiman.api.transport import TransportError
from gavicore.models import ProcessRequest

HUB_URL = "https://hub.test/prefix/hub/api"
HUB_TOKEN = "hub-credential"  # noqa: S105 - synthetic credential for mock HTTP


async def invoke(method, *args, **kwargs):
    result = method(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


@pytest.fixture(params=[Client, AsyncClient], ids=["sync", "async"])
def kind(request):
    return request.param


def client_for(kind, **kwargs):
    return kind(
        api_url="https://processing.test/api",
        auth=JupyterHubAuth(hub_api_url=HUB_URL, hub_api_token=HUB_TOKEN),
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("trailing_slash", [False, True])
async def test_current_token_is_retrieved_for_each_request(kind, hub, trailing_slash):
    adapter = JupyterHubAuth(
        hub_api_url=HUB_URL + ("/" if trailing_slash else ""), hub_api_token=HUB_TOKEN
    )
    client = kind(api_url="https://processing.test/api", auth=adapter)
    assert not hub.requests
    assert not hub.clients
    try:
        await invoke(client.login)
        assert [r.url.host for r in hub.requests] == ["hub.test"]
        hub.requests.clear()
        assert (await invoke(client.get_conformance)).conformsTo == []
        hub.body = {"auth_state": {"access_token": "upstream-second"}}
        await invoke(client.get_conformance)
        assert len(hub.clients) == 1
        assert [r.url.host for r in hub.requests] == [
            "hub.test",
            "processing.test",
            "hub.test",
            "processing.test",
        ]
        assert [r.headers["authorization"] for r in hub.requests[1::2]] == [
            "Bearer upstream-first",
            "Bearer upstream-second",
        ]
        assert client.token is None
        public = json.dumps(client.config.to_file_dict()) + repr(adapter)
        for secret in (HUB_TOKEN, "upstream-first", "upstream-second"):
            assert secret not in public
    finally:
        await invoke(client.close)
    assert hub.clients[0].is_closed


@pytest.mark.asyncio
async def test_lookup_does_not_copy_processing_headers_or_query(kind, hub):
    client = client_for(kind)
    try:
        await invoke(
            client.get_conformance,
            headers={"X-Processing": "private", "Cookie": "session=private"},
            params={"private": "value"},
            timeout=2.5,
        )
        lookup, processing = hub.requests
        assert "x-processing" not in lookup.headers
        assert "cookie" not in lookup.headers
        assert lookup.url.query == b""
        assert lookup.content == b""
        assert lookup.extensions["timeout"] == httpx2.Timeout(2.5).as_dict()
        assert processing.headers["X-Processing"] == "private"
        assert processing.headers["Cookie"] == "session=private"
        assert processing.url.query == b"private=value"
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 500, 302])
async def test_http_failure_stops_processing_post(kind, hub, status):
    hub.status = status
    hub.body = {"secret": "must-not-appear"}
    client = client_for(kind)
    try:
        with pytest.raises(TransportError) as caught:
            await invoke(client.execute_process, "p", ProcessRequest(inputs={}))
        assert isinstance(caught.value.__cause__, httpx2.HTTPStatusError)
        assert str(status) in str(caught.value)
        assert "must-not-appear" not in str(caught.value)
        assert [r.url.host for r in hub.requests] == ["hub.test"]
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [httpx2.ReadTimeout, httpx2.ConnectError])
async def test_network_failure_is_propagated_without_processing(kind, hub, error_type):
    hub.error = error_type("Hub unavailable")
    client = client_for(kind)
    try:
        with pytest.raises(TransportError) as caught:
            await invoke(client.execute_process, "p", ProcessRequest(inputs={}))
        assert caught.value.__cause__ is hub.error
        assert len(hub.requests) == 1
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        "secret",
        {},
        {"auth_state": None},
        {"auth_state": []},
        {"auth_state": {}},
        {"auth_state": {"access_token": None}},
        {"auth_state": {"access_token": 42}},
        {"auth_state": {"access_token": ""}},
        {"auth_state": {"access_token": "bad\r\nsecret"}},
        {"auth_state": {"access_token": "nonascii-\u00e9"}},
    ],
)
async def test_invalid_auth_state_blocks_post_and_allows_later_recovery(
    kind, hub, body
):
    hub.body = body
    client = client_for(kind)
    try:
        with pytest.raises(JupyterHubAuthError) as caught:
            await invoke(client.execute_process, "p", ProcessRequest(inputs={}))
        assert "secret" not in str(caught.value)
        assert len(hub.requests) == 1
        hub.body = {"auth_state": {"access_token": "recovered"}}
        await invoke(client.get_conformance)
        assert hub.requests[-1].headers["authorization"] == "Bearer recovered"
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_malformed_json_does_not_expose_response(kind, hub):
    hub.content = b"not-json-secret"
    client = client_for(kind)
    try:
        with pytest.raises(JupyterHubAuthError, match="valid JSON") as caught:
            await invoke(client.get_conformance)
        assert "not-json-secret" not in str(caught.value)
        assert caught.value.__suppress_context__
        assert len(hub.requests) == 1
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_processing_401_is_not_replayed_and_old_token_is_not_reused(kind, hub):
    client = client_for(kind)
    try:
        hub.processing_status = 401
        with pytest.raises(ClientError):
            await invoke(client.execute_process, "p", ProcessRequest(inputs={"x": 1}))
        assert [r.method for r in hub.requests] == ["GET", "POST"]
        assert json.loads(hub.requests[-1].content)["inputs"] == {"x": 1}
        hub.status = 403
        with pytest.raises(TransportError):
            await invoke(client.get_conformance)
        assert [r.url.host for r in hub.requests] == [
            "hub.test",
            "processing.test",
            "hub.test",
        ]
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_request_auth_override_skips_hub(kind, hub):
    client = client_for(kind)
    try:
        await invoke(client.get_conformance, auth=None)
        await invoke(
            client.get_conformance, headers={"Authorization": "Bearer explicit"}
        )
        assert [r.url.host for r in hub.requests] == ["processing.test"] * 2
        assert "authorization" not in hub.requests[0].headers
        assert hub.requests[1].headers["authorization"] == "Bearer explicit"
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_redirected_lookup_is_rejected(kind, hub):
    def redirect(request):
        hub.requests.append(request)
        if request.url.path.endswith("/user"):
            return httpx2.Response(302, headers={"Location": "/other"})
        return httpx2.Response(200, json=hub.body)

    adapter = JupyterHubAuth(hub_api_url=HUB_URL, hub_api_token=HUB_TOKEN)
    cls = httpx2.AsyncClient if kind is AsyncClient else httpx2.Client
    client = cls(auth=adapter, transport=httpx2.MockTransport(redirect))
    try:
        with pytest.raises(JupyterHubAuthError, match="redirected"):
            await invoke(client.get, "https://processing.test", follow_redirects=True)
        assert all(r.url.host == "hub.test" for r in hub.requests)
    finally:
        await invoke(client.aclose if kind is AsyncClient else client.close)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "/hub/api",
        "ftp://hub.test",
        "https://user:secret@hub.test",
        "https://hub.test/?secret=1",
        "https://hub.test/#secret",
        "https://[bad",
        None,
    ],
)
def test_invalid_hub_url_is_rejected_without_echoing_it(url):
    with pytest.raises(ValueError, match="hub_api_url") as caught:
        JupyterHubAuth(hub_api_url=url, hub_api_token=HUB_TOKEN)
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize(
    "token", [None, "", " ", "bad\r\nsecret", "bad\tsecret", "\u00e9"]
)
def test_invalid_hub_token_is_rejected_without_echoing_it(token):
    with pytest.raises(ValueError, match="hub_api_token") as caught:
        JupyterHubAuth(hub_api_url=HUB_URL, hub_api_token=token)
    assert "secret" not in str(caught.value)


def test_private_network_http_url_is_supported():
    adapter = JupyterHubAuth(
        hub_api_url="http://hub:8081/hub/api", hub_api_token=HUB_TOKEN
    )
    request = httpx2.Request("POST", "https://processing.test", content=b"private")
    flow = adapter.auth_flow(request)
    lookup = next(flow)
    assert str(lookup.url) == "http://hub:8081/hub/api/user"
    assert lookup.extensions["timeout"] == httpx2.Timeout(5).as_dict()
    assert lookup.content == b""
    flow.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_type", [None, "auto", "jupyter"])
async def test_discovery_and_required_auth_verify_then_refetch(
    kind, hub, hub_environment, auth_type
):
    client = kind(
        api_url="https://processing.test",
        auth={"auth_type": auth_type} if auth_type else None,
    )
    assert not hub.requests and not hub.clients
    try:
        await invoke(client.login, interactive=False)
        assert [r.url.host for r in hub.requests] == ["hub.test"]
        hub.body = {"auth_state": {"access_token": "changed"}}
        await invoke(client.get_conformance)
        assert [r.url.host for r in hub.requests] == [
            "hub.test",
            "hub.test",
            "processing.test",
        ]
        assert hub.requests[-1].headers["authorization"] == "Bearer changed"
        assert len(hub.clients) == 1
        assert client.token is None
        serialized = json.dumps(client.config.to_file_dict())
        assert HUB_TOKEN not in serialized and "changed" not in serialized
        with pytest.raises(ValueError, match="cannot be saved"):
            await invoke(client.login, save=True)
    finally:
        await invoke(client.logout)
    assert hub.clients[0].is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "environment,auth_type",
    [("absent", "auto"), ("absent", "none"), ("valid", "none"), ("invalid", "none")],
)
async def test_anonymous_without_candidate_or_with_explicit_none(
    kind, hub, monkeypatch, environment, auth_type
):
    if environment == "invalid":
        monkeypatch.setenv("JUPYTERHUB_API_URL", "malformed")
    elif environment == "valid":
        monkeypatch.setenv("JUPYTERHUB_API_URL", HUB_URL)
        monkeypatch.setenv("JUPYTERHUB_API_TOKEN", HUB_TOKEN)
    client = kind(api_url="https://processing.test", auth={"auth_type": auth_type})
    try:
        await invoke(client.login, interactive=False)
        await invoke(client.get_conformance)
        await invoke(client.get_conformance)
        assert [r.url.host for r in hub.requests] == ["processing.test"] * 2
        assert all("authorization" not in r.headers for r in hub.requests)
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize(
    "values",
    [
        (HUB_URL, None),
        (None, HUB_TOKEN),
        ("", ""),
        ("https://user:secret@hub.test", HUB_TOKEN),
        (HUB_URL, "bad\nsecret"),
    ],
)
async def test_invalid_environment_never_sends_processing_request(
    kind, hub, monkeypatch, required, values
):
    for name, value in zip(("JUPYTERHUB_API_URL", "JUPYTERHUB_API_TOKEN"), values):
        if value is not None:
            monkeypatch.setenv(name, value)
    client = kind(
        api_url="https://processing.test",
        auth={"auth_type": "jupyter"} if required else None,
    )
    try:
        with pytest.raises(JupyterHubAuthError) as caught:
            await invoke(client.execute_process, "p", ProcessRequest(inputs={}))
        assert "secret" not in str(caught.value)
        assert not hub.requests
        monkeypatch.setenv("JUPYTERHUB_API_URL", HUB_URL)
        monkeypatch.setenv("JUPYTERHUB_API_TOKEN", HUB_TOKEN)
        await invoke(client.get_conformance)
        assert [r.url.host for r in hub.requests] == ["hub.test", "processing.test"]
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["login", "get_conformance"])
async def test_required_auth_without_environment_fails(kind, hub, operation):
    client = kind(api_url="https://processing.test", auth={"auth_type": "jupyter"})
    try:
        with pytest.raises(JupyterHubAuthError, match="requires both"):
            await invoke(getattr(client, operation))
        assert not hub.requests
    finally:
        await invoke(client.logout)


@pytest.mark.asyncio
@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("failure", ["missing-token", "http", "network"])
async def test_candidate_failure_blocks_login_and_processing_without_fallback(
    kind, hub, hub_environment, required, failure
):
    if failure == "missing-token":
        hub.body = {"auth_state": {}}
        login_error, request_error = JupyterHubAuthError, JupyterHubAuthError
    elif failure == "http":
        hub.status = 403
        login_error, request_error = httpx2.HTTPStatusError, TransportError
    else:
        hub.error = httpx2.ReadTimeout("Hub unavailable")
        login_error, request_error = httpx2.ReadTimeout, TransportError
    client = kind(
        api_url="https://processing.test",
        auth={"auth_type": "jupyter"} if required else None,
    )
    try:
        with pytest.raises(login_error):
            await invoke(client.login, interactive=False)
        with pytest.raises(request_error):
            await invoke(client.execute_process, "p", ProcessRequest(inputs={}))
        assert [r.url.host for r in hub.requests] == ["hub.test"] * 2
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize(
    "override",
    [
        {"auth": None},
        {"headers": {"authorization": "Bearer override"}},
        {"auth": httpx2.BasicAuth("user", "password")},
    ],
)
async def test_request_override_defers_discovery_and_reuses_session(
    kind, hub, monkeypatch, required, override
):
    monkeypatch.setenv("JUPYTERHUB_API_URL", "invalid")
    client = kind(
        api_url="https://processing.test",
        auth={"auth_type": "jupyter"} if required else None,
    )
    try:
        await invoke(client.get_conformance, **override)
        assert [r.url.host for r in hub.requests] == ["processing.test"]
        monkeypatch.setenv("JUPYTERHUB_API_URL", HUB_URL)
        monkeypatch.setenv("JUPYTERHUB_API_TOKEN", HUB_TOKEN)
        await invoke(client.get_conformance)
        assert [r.url.host for r in hub.requests] == [
            "processing.test",
            "hub.test",
            "processing.test",
        ]
        assert hub.requests[-1].headers["authorization"] == "Bearer upstream-first"
        assert len(hub.clients) == 1
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth",
    [
        {"auth_type": "token", "access_token": "configured"},
        httpx2.BasicAuth("user", "password"),
    ],
)
async def test_explicit_auth_wins_over_invalid_hub_environment(
    kind, hub, monkeypatch, auth
):
    monkeypatch.setenv("JUPYTERHUB_API_URL", "invalid")
    client = kind(api_url="https://processing.test", auth=auth)
    try:
        await invoke(client.get_conformance)
        assert [r.url.host for r in hub.requests] == ["processing.test"]
        assert "authorization" in hub.requests[0].headers
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_incomplete_explicit_auth_does_not_fall_back_to_hub(
    kind, hub, hub_environment
):
    from cuiman.api.auth import LoginRequiredError

    client = kind(api_url="https://processing.test", auth={"auth_type": "token"})
    try:
        with pytest.raises(LoginRequiredError):
            await invoke(client.get_conformance)
        assert not hub.requests
    finally:
        await invoke(client.close)


def test_settings_roundtrip_and_environment_precedence(tmp_path, monkeypatch):
    from pydantic_settings import SettingsConfigDict

    from cuiman import ClientConfig
    from cuiman.api.auth import AutoAuthConfig, JupyterAuthConfig, NoAuthConfig

    class BrandedConfig(ClientConfig):
        model_config = SettingsConfigDict(env_prefix="BRANDED_")

    path = tmp_path / "profile"
    BrandedConfig(auth=NoAuthConfig()).write(path)
    assert isinstance(BrandedConfig.create(config_path=path).auth, NoAuthConfig)
    monkeypatch.setenv("EOZILLA_AUTH__AUTH_TYPE", "auto")
    assert isinstance(ClientConfig.create().auth, AutoAuthConfig)
    assert isinstance(BrandedConfig.create(config_path=path).auth, NoAuthConfig)
    monkeypatch.setenv("BRANDED_AUTH__AUTH_TYPE", "auto")
    assert isinstance(BrandedConfig.create(config_path=path).auth, AutoAuthConfig)
    config = BrandedConfig.create(config_path=path, auth=JupyterAuthConfig())
    assert isinstance(config.auth, JupyterAuthConfig)
    config.write(path)
    assert isinstance(BrandedConfig.from_file(path).auth, JupyterAuthConfig)
    monkeypatch.setenv("EOZILLA_AUTH__AUTH_TYPE", "jupyter")
    assert isinstance(ClientConfig.create().auth, JupyterAuthConfig)


@pytest.mark.asyncio
async def test_saved_none_profile_stays_anonymous_until_explicitly_overridden(
    kind, hub, hub_environment, tmp_path
):
    from cuiman import ClientConfig

    path = tmp_path / "existing-profile"
    ClientConfig(api_url="https://processing.test", auth={"auth_type": "none"}).write(
        path
    )
    client = kind(config_path=path, auth=None)
    try:
        await invoke(client.get_conformance)
        assert [r.url.host for r in hub.requests] == ["processing.test"]
        assert "authorization" not in hub.requests[-1].headers
    finally:
        await invoke(client.close)
    client = kind(config_path=path, auth={"auth_type": "auto"})
    try:
        await invoke(client.get_conformance)
        assert [r.url.host for r in hub.requests] == [
            "processing.test",
            "hub.test",
            "processing.test",
        ]
        assert ClientConfig.from_file(path).auth.auth_type == "none"
        assert client.config.auth.auth_type == "auto"
    finally:
        await invoke(client.close)


@pytest.mark.parametrize("auth_type", ["auto", "jupyter"])
def test_cli_login_verifies_hub_without_saving(hub, hub_environment, auth_type):
    from typer.testing import CliRunner

    from cuiman import ClientConfig
    from cuiman.cli.cli import new_cli

    ClientConfig(
        api_url="https://processing.test", auth={"auth_type": auth_type}
    ).write()
    result = CliRunner().invoke(new_cli(), ["login", "--no-input"])
    assert result.exit_code == 0, result.output
    assert "Login completed" in result.output
    assert [r.url.host for r in hub.requests] == ["hub.test"]
    assert hub.clients[0].is_closed


@pytest.mark.parametrize("command", [["login", "--no-input"], ["list-processes"]])
def test_cli_required_hub_failure_is_actionable(command):
    from typer.testing import CliRunner

    from cuiman import ClientConfig
    from cuiman.cli.cli import new_cli

    ClientConfig(
        api_url="https://processing.test", auth={"auth_type": "jupyter"}
    ).write()
    result = CliRunner().invoke(new_cli(), command)
    assert result.exit_code == 1, result.output
    assert "JUPYTERHUB_API_URL" in result.output
    assert "Login completed" not in result.output


@pytest.mark.parametrize("command", [["login", "--no-input"], ["list-processes"]])
@pytest.mark.parametrize("auth_type", ["auto", "none"])
def test_cli_auth_selection_from_environment(
    hub, hub_environment, command, auth_type, monkeypatch
):
    from typer.testing import CliRunner

    from cuiman import ClientConfig
    from cuiman.cli.cli import new_cli

    ClientConfig(api_url="https://processing.test", auth={"auth_type": "none"}).write()
    monkeypatch.setenv("EOZILLA_AUTH__AUTH_TYPE", auth_type)
    result = CliRunner().invoke(new_cli(), command)
    assert result.exit_code == 0, result.output
    assert any(r.url.host == "hub.test" for r in hub.requests) is (auth_type == "auto")
    assert ClientConfig.from_file().auth.auth_type == "none"


@pytest.mark.parametrize("auth_type", ["auto", "none", "jupyter"])
def test_cli_configure_persists_auth_selection(tmp_path, auth_type):
    from typer.testing import CliRunner

    from cuiman import ClientConfig
    from cuiman.cli.cli import new_cli

    path = tmp_path / "profile"
    args = [
        "configure",
        "--config",
        str(path),
        "--api-url",
        "https://processing.test",
        "--auth-type",
        auth_type,
    ]
    result = CliRunner().invoke(new_cli(), args)
    assert result.exit_code == 0, result.output
    config = ClientConfig.from_file(path)
    assert config.to_file_dict() == {
        "api_url": "https://processing.test/",
        "auth": {"auth_type": auth_type},
    }
