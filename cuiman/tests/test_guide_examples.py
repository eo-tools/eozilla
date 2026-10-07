"""Exercise the code included in the user guides without a running service."""

import html
import re
import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest
import xarray as xr
from markdown import markdown
from remotestate import ServeResult
from typer.testing import CliRunner

from cuiman import Client, ClientConfig
from cuiman.api.opener import JobResultOpenContext, JobResultOpenerRegistry
from cuiman.app import App
from cuiman.cli import cli
from examples.guides.cuiman import api, app, openers
from gavicore.models import JobInfo, JobResults, Link, ProcessRequest
from procodile import Job
from wraptile.services.local.testing import service

REQUEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples/guides/cuiman/simulate-scene-request.json"
)


@pytest.fixture
def opener_registry(monkeypatch):
    """Keep example registrations independent of other client tests."""
    registry = JobResultOpenerRegistry.create_default()
    monkeypatch.setattr(
        ClientConfig,
        "get_job_result_opener_registry",
        classmethod(lambda cls: registry),
    )
    return registry


@pytest.fixture
def client():
    result = Mock(spec=Client)
    result.execute_process.return_value = JobInfo(jobID="new-job-42", status="accepted")
    result.open_job_result.return_value.sizes = {"time": 2, "lat": 4, "lon": 4}
    return result


@pytest.mark.parametrize("status", list(api.JobStatus))
def test_api_session_uses_submitted_id_and_closes(monkeypatch, client, status):
    monkeypatch.setattr(api, "create_client", lambda: client)
    client.get_job.return_value = JobInfo(jobID="new-job-42", status=status)

    assert api.example_session() == "new-job-42"

    client.get_process.assert_called_once_with("primes_between")
    client.execute_process.assert_called_once_with(
        "primes_between", request=ProcessRequest(inputs={"min_val": 10, "max_val": 80})
    )
    client.get_job.assert_called_once_with("new-job-42")
    if status == api.JobStatus.successful:
        client.get_job_results.assert_called_once_with("new-job-42")
    else:
        client.get_job_results.assert_not_called()
    client.close.assert_called_once()


def test_api_closes_after_request_error(monkeypatch, client):
    monkeypatch.setattr(api, "create_client", lambda: client)
    client.get_processes.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        api.example_session()
    client.close.assert_called_once()
    client.execute_process.assert_not_called()


def test_create_client_selects_local_service_without_login(monkeypatch):
    login = Mock(side_effect=AssertionError("unexpected login"))
    monkeypatch.setattr(Client, "login", login)
    client = api.create_client()
    try:
        assert client.config.api_url == "http://127.0.0.1:8008/"
        assert client.config.auth.auth_type == "none"
        login.assert_not_called()
    finally:
        client.close()


def test_failure_example_matches_local_process(client, monkeypatch):
    assert api.submit_failure_example(client) == "new-job-42"
    process_id = client.execute_process.call_args.args[0]
    request = client.execute_process.call_args.kwargs["request"]
    monkeypatch.setattr("wraptile.services.local.testing.time.sleep", lambda _: None)
    job = Job.create(service.process_registry.get(process_id), request)
    assert job.run() is None
    assert job.job_info.status == api.JobStatus.failed
    assert job.job_info.message == "Woke up too early"


def test_prime_example_matches_local_process(monkeypatch, client):
    monkeypatch.setattr(api, "create_client", lambda: client)
    api.example_session()
    process_id = client.execute_process.call_args.args[0]
    request = client.execute_process.call_args.kwargs["request"]
    result = Job.create(service.process_registry.get(process_id), request).run()
    assert result.root["return_value"] == [
        11,
        13,
        17,
        19,
        23,
        29,
        31,
        37,
        41,
        43,
        47,
        53,
        59,
        61,
        67,
        71,
        73,
        79,
    ]


@pytest.mark.parametrize("display", ["browser", "notebook"])
def test_open_app_retains_client_for_interaction(monkeypatch, client, display):
    monkeypatch.setattr(app, "Client", Mock(return_value=client))
    assert app.open_app(display) == (client, client.show_app.return_value)
    client.show_app.assert_called_once_with(display=display, height=640)
    client.close.assert_not_called()


def test_app_launch_error_closes_client(monkeypatch, client):
    monkeypatch.setattr(app, "Client", Mock(return_value=client))
    client.show_app.side_effect = RuntimeError("launch failed")
    with pytest.raises(RuntimeError, match="launch failed"):
        app.open_app()
    client.close.assert_called_once()


def test_update_app_preserves_other_inputs_and_outputs():
    client_app = App(App.create_remote_store(), Mock(spec=ServeResult))
    with pytest.raises(ValueError, match="Open the sleep_a_while"):
        app.set_duration(client_app)
    request = ProcessRequest(
        inputs={"duration": 10, "fail": True},
        outputs={"return_value": {"transmissionMode": "value"}},
    )
    client_app.set_process_request("sleep_a_while", request)
    app.set_duration(client_app, 5)
    updated = client_app.get_process_request("sleep_a_while")
    assert updated.inputs == {"duration": 5, "fail": True}
    assert updated.outputs == request.outputs


@pytest.mark.parametrize("stop_error", [None, RuntimeError("stop failed")])
def test_app_cleanup_closes_client_even_if_stop_fails(client, stop_error):
    client_app = Mock(spec=App)
    client_app.serve_result.stop.side_effect = stop_error
    if stop_error:
        with pytest.raises(RuntimeError, match="stop failed"):
            app.close_app(client, client_app)
    else:
        app.close_app(client, client_app)
    client_app.serve_result.stop.assert_called_once()
    client.close.assert_called_once()


def test_app_script_stops_on_interrupt(monkeypatch, client):
    monkeypatch.setattr("cuiman.Client", Mock(return_value=client))
    monkeypatch.setattr("time.sleep", Mock(side_effect=KeyboardInterrupt))
    runpy.run_path(app.__file__, run_name="__main__")
    client.show_app.return_value.serve_result.stop.assert_called_once()
    client.close.assert_called_once()


def test_api_script_runs_only_one_submission(monkeypatch, client):
    monkeypatch.setattr("cuiman.Client", Mock(return_value=client))
    runpy.run_path(api.__file__, run_name="__main__")
    client.execute_process.assert_called_once()
    client.close.assert_called_once()


def test_cli_scene_request_validates_offline():
    result = CliRunner().invoke(
        cli, ["validate-request", "simulate_scene", "--request", str(REQUEST_PATH)]
    )
    assert result.exit_code == 0, result.output


def test_submit_scene_validates_before_connecting(client, tmp_path):
    assert openers.submit_scene(client, REQUEST_PATH) == "new-job-42"
    process_id = client.execute_process.call_args.args[0]
    request = client.execute_process.call_args.kwargs["request"]
    assert process_id == "simulate_scene"
    assert request.inputs["output_path"] == "guide-scene.zarr"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text('{"inputs": []}', encoding="utf-8")
    client.reset_mock()
    with pytest.raises(ValueError):
        openers.submit_scene(client, invalid_path)
    client.execute_process.assert_not_called()


@pytest.fixture
def scene_context(tmp_path, request):
    filename = getattr(request, "param", "scene.zarr")
    scene_request = ProcessRequest.model_validate_json(
        REQUEST_PATH.read_text(encoding="utf-8")
    )
    scene_request.inputs["output_path"] = str(tmp_path / filename)
    job = Job.create(service.process_registry.get("simulate_scene"), scene_request)
    results = job.run()
    assert job.job_info.status == api.JobStatus.successful
    return JobResultOpenContext(
        config=ClientConfig(auth={"auth_type": "none"}),
        job_id=job.job_info.jobID,
        job_results=results,
        output_name="return_value",
        data_type=xr.Dataset,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("scene_context", ["scene with spaces.zarr"], indirect=True)
async def test_custom_opener_reads_actual_local_scene(scene_context):
    opener = openers.LocalZarrOpener()
    assert await opener.accept_job_result(scene_context)
    dataset = await opener.open_job_result(scene_context)
    try:
        assert dict(dataset.sizes) == {"time": 2, "lat": 4, "lon": 4}
        assert set(dataset.data_vars) == {"a", "b"}
        assert float(dataset.a.sum()) == 0
    finally:
        dataset.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,output_name,data_type,media_type",
    [
        (42, "return_value", xr.Dataset, None),
        (
            Link(href="file:///scene.zarr", type="application/zarr"),
            "missing",
            xr.Dataset,
            None,
        ),
        (
            Link(href="file:///scene.zarr", type="application/zarr"),
            "return_value",
            str,
            None,
        ),
        (
            Link(href="https://example.com/scene.zarr", type="application/zarr"),
            "return_value",
            xr.Dataset,
            None,
        ),
        (
            Link(href="file://remote/scene.zarr", type="application/zarr"),
            "return_value",
            xr.Dataset,
            None,
        ),
        (
            Link(href="file:///scene.zarr", type="application/zarr"),
            "return_value",
            xr.Dataset,
            "text/plain",
        ),
    ],
)
async def test_custom_opener_rejects_incompatible_output(
    value, output_name, data_type, media_type
):
    ctx = JobResultOpenContext(
        config=ClientConfig(auth={"auth_type": "none"}),
        job_id="existing-job",
        job_results=JobResults(root={"return_value": value}),
        output_name=output_name,
        data_type=data_type,
        _media_type=media_type,
    )
    assert not await openers.LocalZarrOpener().accept_job_result(ctx)


@pytest.mark.parametrize("custom", [False, True])
def test_openers_use_real_client_and_restore_registry(
    monkeypatch, scene_context, custom, opener_registry
):
    client = api.create_client()
    registry = client.config.get_job_result_opener_registry()
    original = registry.opener_types
    monkeypatch.setattr(
        client, "get_job", lambda _: JobInfo(jobID="existing-job", status="successful")
    )
    monkeypatch.setattr(client, "get_job_results", lambda _: scene_context.job_results)
    try:
        open_fn = openers.open_with_custom_opener if custom else openers.open_scene
        dataset = open_fn(client, "existing-job")
        try:
            assert dict(dataset.sizes) == {"time": 2, "lat": 4, "lon": 4}
        finally:
            dataset.close()
        assert registry.opener_types == original
    finally:
        client.close()


def test_custom_registration_restored_on_failure(monkeypatch, opener_registry):
    client = api.create_client()
    registry = client.config.get_job_result_opener_registry()
    original = registry.opener_types
    monkeypatch.setattr(
        client, "open_job_result", Mock(side_effect=RuntimeError("unreadable"))
    )
    try:
        with pytest.raises(RuntimeError, match="unreadable"):
            openers.open_with_custom_opener(client, "existing-job")
        assert registry.opener_types == original
    finally:
        client.close()


@pytest.mark.parametrize("error", [None, RuntimeError("unreadable")])
def test_opener_session_closes_resources(monkeypatch, client, error):
    monkeypatch.setattr(openers, "Client", Mock(return_value=client))
    monkeypatch.chdir(REQUEST_PATH.parents[3])
    client.open_job_result.side_effect = error
    if error:
        with pytest.raises(RuntimeError, match="unreadable"):
            openers.example_session()
    else:
        assert openers.example_session() == "new-job-42"
        client.open_job_result.return_value.close.assert_called_once()
    assert client.open_job_result.call_args.args == ("new-job-42",)
    client.execute_process.assert_called_once()
    client.close.assert_called_once()


def test_opener_script_runs_and_closes(monkeypatch, client):
    monkeypatch.setattr("cuiman.Client", Mock(return_value=client))
    monkeypatch.chdir(REQUEST_PATH.parents[3])
    runpy.run_path(openers.__file__, run_name="__main__")
    client.execute_process.assert_called_once()
    client.open_job_result.return_value.close.assert_called_once()
    client.close.assert_called_once()


def test_update_app_initializes_empty_inputs():
    client_app = App(App.create_remote_store(), Mock(spec=ServeResult))
    client_app.set_process_request("sleep_a_while", ProcessRequest(inputs=None))
    app.set_duration(client_app)
    assert client_app.get_process_request("sleep_a_while").inputs == {"duration": 2}


@pytest.mark.parametrize("module", [api, app, openers])
def test_importing_examples_does_not_create_clients(monkeypatch, module):
    constructor = Mock(side_effect=AssertionError("unexpected client"))
    monkeypatch.setattr("cuiman.Client", constructor)
    runpy.run_path(module.__file__)
    constructor.assert_not_called()


@pytest.mark.parametrize(
    "guide,start_block", [("api", 0), ("app", 0), ("app", 1), ("openers", 0)]
)
def test_rendered_python_walkthrough_runs_in_order(
    monkeypatch, client, guide, start_block
):
    """Ensure included snippets contain the imports and state their calls need."""
    root = REQUEST_PATH.parents[3]
    monkeypatch.chdir(root)
    monkeypatch.setattr("cuiman.Client", Mock(return_value=client))
    monkeypatch.setattr(app, "Client", Mock(return_value=client))
    client_app = App(App.create_remote_store(), Mock(spec=ServeResult))
    client_app.set_process_request(
        "sleep_a_while", ProcessRequest(inputs={"duration": 2})
    )
    client.show_app.return_value = client_app
    client.get_job.return_value = JobInfo(jobID="new-job-42", status="successful")
    source = (root / "docs/cuiman/guides" / f"{guide}.md").read_text(encoding="utf-8")
    rendered = markdown(
        source,
        extensions=["fenced_code", "pymdownx.snippets"],
        extension_configs={
            "pymdownx.snippets": {
                "base_path": str(root),
                "check_paths": True,
                "dedent_subsections": True,
            }
        },
    )
    blocks = re.findall(
        r'<pre><code class="language-python">(.*?)</code></pre>', rendered, re.DOTALL
    )
    assert blocks
    namespace = {}
    for block in blocks[start_block:]:
        exec(compile(html.unescape(block), f"{guide}.md", "exec"), namespace)  # noqa: S102
    client.close.assert_called()
