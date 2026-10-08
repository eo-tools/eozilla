import json
from pathlib import Path
from unittest.mock import patch

import httpx2
import pytest
import xarray as xr
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from gavicore.models import JobResults, Link, ProcessRequest
from procodile import Job
from wraptile.services.local._testing_stac import mount_artifacts, output_settings
from wraptile.services.local.testing import _TestingService, service


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    directory = tmp_path / "artifacts with spaces"
    monkeypatch.setenv("EOZILLA_TESTING_STAC_DIR", str(directory))
    monkeypatch.setenv("EOZILLA_TESTING_STAC_URL", "http://testing.test/testing-stac/")
    return directory


@pytest.mark.asyncio
@pytest.mark.parametrize("inline", [False, True])
async def test_process_outputs_products_and_http(inline, artifacts):
    process_id = "create_inline_stac" if inline else "create_linked_stac"
    process = service.process_registry.get(process_id)
    assert set(process.description.outputs) == {
        "item",
        "item_collection",
        "report",
        "item_count",
        "optional",
    }
    assert process.description.inputs["item_count"].schema_.minimum == 1
    assert process.description.inputs["item_count"].schema_.maximum == 4
    job = Job.create(process, ProcessRequest(inputs={"item_count": 2}))
    results = job.run()
    assert isinstance(results, JobResults), job.job_info.message
    outputs = results.model_dump(mode="json")
    assert outputs["item_count"] == 2 and outputs["optional"] is None
    assert isinstance(results.root["report"], Link)
    assert isinstance(results.root["item"], dict if inline else Link)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"])
    mount_artifacts(app)
    mount_artifacts(app)
    assert sum(route.name == "testing-stac" for route in app.routes) == 1
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://testing.test"
    ) as client:
        if inline:
            document = outputs["item"]
            collection = outputs["item_collection"]
        else:
            response = await client.get(
                outputs["item"]["href"], headers={"origin": "http://app.test"}
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == "*"
            document = response.json()
            collection = (await client.get(outputs["item_collection"]["href"])).json()
        assert document["id"] == "scene-1"
        assert len(collection["features"]) == 2
        assert collection["testing:complete"] is True
        assert set(document["assets"]) == {"data", "report", "products"}
        assert not document["assets"]["products"]["href"].endswith("/")
        assert all(
            member["assets"]["data"]["href"].startswith(member["id"] + "/")
            for member in collection["features"]
        )
        report = await client.get(outputs["report"]["href"])
        assert report.text == "scene,mean_ndvi\nscene-1,1.5\n"
        run_dir = next(artifacts.iterdir())
        assert (
            json.loads((run_dir / "scene-1.json").read_text(encoding="utf-8"))
            == document
        )
        for index in range(2):
            with xr.open_zarr(
                str(run_dir / f"scene-{index + 1}/products/data.zarr")
            ) as dataset:
                assert dataset["ndvi"].values.tolist() == [
                    [index, index + 1],
                    [index + 2, index + 3],
                ]
        # No directory enumeration or traversal outside the declared test root.
        assert (await client.get("/testing-stac/")).status_code == 404
        assert (await client.get("/testing-stac/%2e%2e/outside.txt")).status_code == 404
    second = Job.create(process, ProcessRequest(inputs={"item_count": 1})).run()
    assert second.root["item_count"] == 1
    assert len(list(artifacts.iterdir())) == 2
    # Cleanup is explicit: every run is confined to the configured directory.
    assert all(directory.parent == artifacts for directory in artifacts.iterdir())


def test_testing_configuration_mounts_only_testing_service(artifacts):
    app = FastAPI()
    testing = _TestingService(title="test")
    with patch("wraptile.app.app", app):
        testing.configure(max_workers=1)
    assert artifacts.is_dir()
    assert app.routes[-1].name == "testing-stac"
    testing.executor.shutdown()


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp",
        "http://user:secret@host/test",
        "http://host/test?secret=1",
        "http://host/test#fragment",
        "relative",
    ],
)
def test_invalid_public_base(monkeypatch, url):
    monkeypatch.setenv("EOZILLA_TESTING_STAC_URL", url)
    with pytest.raises(ValueError, match="absolute HTTP URL"):
        output_settings()


def test_default_output_configuration(monkeypatch):
    monkeypatch.delenv("EOZILLA_TESTING_STAC_DIR", raising=False)
    monkeypatch.delenv("EOZILLA_TESTING_STAC_URL", raising=False)
    directory, base = output_settings()
    assert directory == Path(".pixi/testing-stac").resolve()
    assert base == "http://localhost:8008/testing-stac"


@pytest.mark.parametrize("process_id", ["create_inline_stac", "create_linked_stac"])
@pytest.mark.parametrize("count", [0, 5])
def test_input_bounds_reject_before_generation(process_id, count, artifacts):
    process = service.process_registry.get(process_id)
    with pytest.raises(ValidationError):
        Job.create(process, ProcessRequest(inputs={"item_count": count}))
    assert not artifacts.exists()
