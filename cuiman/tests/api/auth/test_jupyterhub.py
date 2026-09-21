"""JupyterHub token retrieval through native HTTPX2 and both Cuiman clients."""

import inspect
import json
from types import SimpleNamespace

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


@pytest.fixture
def hub(monkeypatch):
    state = SimpleNamespace(
        requests=[],
        clients=[],
        body={"auth_state": {"access_token": "upstream-first"}},
        content=None,
        status=200,
        processing_status=200,
        error=None,
    )

    def handle(request):
        state.requests.append(request)
        if request.url.host == "hub.test":
            assert request.headers["authorization"] == f"Bearer {HUB_TOKEN}"
            assert request.method == "GET"
            assert request.url.path == "/prefix/hub/api/user"
            if state.error is not None:
                raise state.error
            if state.content is not None:
                return httpx2.Response(state.status, content=state.content)
            return httpx2.Response(state.status, json=state.body)
        assert request.url.host == "processing.test"
        return httpx2.Response(state.processing_status, json={"conformsTo": []})

    for cls in (httpx2.Client, httpx2.AsyncClient):
        original = cls.__init__

        def initialize(self, *args, _original=original, **kwargs):
            kwargs.setdefault("transport", httpx2.MockTransport(handle))
            kwargs.setdefault("trust_env", False)
            _original(self, *args, **kwargs)
            state.clients.append(self)

        monkeypatch.setattr(cls, "__init__", initialize)
    return state


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
        assert not hub.requests
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
