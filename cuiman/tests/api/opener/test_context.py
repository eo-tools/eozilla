#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from cuiman import ClientConfig
from cuiman.api.opener import JobResultOpenContext, JobResultOpenError
from gavicore.models import (
    JobResults,
    Link,
    OutputDescription,
    ProcessDescription,
    QualifiedValue,
    Schema,
)

DEFAULT_JOB_RESULTS = {"a": "out.nc", "b": 2.5, "c": True}

_UNSET_PROCESS_DESCRIPTION = ProcessDescription(id="_", version="0")


def new_ctx(
    job_results: JobResults | None = None,
    output_name: str | None = None,
    data_type: type | None = None,
    outputs: list[str] | None = None,
    process_description: ProcessDescription | None = _UNSET_PROCESS_DESCRIPTION,
    **options: Any,
) -> JobResultOpenContext:
    return JobResultOpenContext(
        config=ClientConfig(api_url="http://localhost:9090"),
        job_id="982a04ee",
        job_results=(
            job_results
            if job_results is not None
            else JobResults(**DEFAULT_JOB_RESULTS)
        ),
        process_description=(
            process_description
            if process_description is not _UNSET_PROCESS_DESCRIPTION
            else ProcessDescription(
                id="test",
                version="0.0.0",
                outputs={
                    k: OutputDescription(title=f"The {k} value", schema=Schema(**{}))
                    for k in outputs
                }
                if outputs
                else None,
            )
        ),
        output_name=(
            output_name if job_results is not None or output_name is not None else "a"
        ),
        data_type=data_type,
        _media_type=None,
        options=options,
    )


qualified_value = QualifiedValue(
    mediaType="application/zarr", value="file://./test.zarr"
)
link_value = Link(type="application/cog", href="file://./test.tif")
inline_value = "file://./test.nc"

ctx_qualified_1 = new_ctx(
    job_results=JobResults(**{"a": qualified_value}), output_name=None
)
ctx_link_1 = new_ctx(job_results=JobResults(**{"b": link_value}), output_name=None)
ctx_inline_1 = new_ctx(job_results=JobResults(**{"c": inline_value}), output_name=None)

ctx_qualified_2 = new_ctx(
    job_results=JobResults(**{"a": qualified_value, "f": False}), output_name="a"
)
ctx_link_2 = new_ctx(
    job_results=JobResults(**{"b": link_value, "f": False}), output_name="b"
)
ctx_inline_2 = new_ctx(
    job_results=JobResults(**{"c": inline_value, "f": False}), output_name="c"
)


def test_output_value():
    assert ctx_qualified_1.output_value == qualified_value
    assert ctx_qualified_2.output_value == qualified_value
    assert ctx_link_1.output_value == link_value
    assert ctx_link_2.output_value == link_value
    assert ctx_inline_1.output_value == inline_value
    assert ctx_inline_2.output_value == inline_value


@pytest.mark.parametrize(
    "results,output_name,message",
    [
        (None, None, "Job results contain no outputs"),
        ({}, None, "Job results contain no outputs"),
        ({}, "a", "Job output 'a' does not exist"),
        ({"a": None}, "missing", "Job output 'missing' does not exist"),
        ({"a": 1, "b": 2}, None, "Multiple job outputs"),
        ({"return_value": 1, "b": 2}, None, "Multiple job outputs"),
    ],
)
def test_invalid_output_selection(results, output_name, message):
    with pytest.raises(JobResultOpenError, match=message):
        new_ctx(job_results=JobResults(root=results), output_name=output_name)


@pytest.mark.parametrize("output_name", [None, "null"])
def test_selected_null_is_valid(output_name):
    ctx = new_ctx(job_results=JobResults(root={"null": None}), output_name=output_name)
    assert ctx.output_name == "null"
    assert ctx.value is None
    assert ctx.output_value is None
    assert ctx.location is None


def test_empty_output_name_is_explicit():
    ctx = new_ctx(job_results=JobResults(root={"": None, "a": 1}), output_name="")
    assert ctx.output_name == ""
    assert ctx.value is None


def test_output_media_type():
    assert ctx_qualified_1.output_media_type == "application/zarr"
    assert ctx_link_1.output_media_type == "application/cog"
    assert ctx_inline_1.output_media_type is None

    ctx = new_ctx()
    assert ctx.output_media_type is None
    ctx._media_type = "text/plain"
    assert ctx.output_media_type == "text/plain"


def test_output_qualified_value():
    assert ctx_qualified_1.output_qualified_value == qualified_value
    assert ctx_link_1.output_qualified_value is None
    assert ctx_inline_1.output_qualified_value is None


def test_output_link():
    assert ctx_qualified_1.output_link is None
    assert ctx_link_1.output_link == link_value
    assert ctx_inline_1.output_link is None


def test_output_link_fom_inline_value():
    link_data = {"href": "s3://xcube/test.zarr", "type": "application/zarr"}
    ctx = new_ctx(
        job_results=JobResults(**{"a": link_data}),
    )
    assert ctx.output_link == Link(**link_data)

    # missing "href"
    link_data = {"path": "s3://xcube/test.zarr", "type": "application/zarr"}
    ctx = new_ctx(
        job_results=JobResults(**{"a": link_data}),
    )
    assert ctx.output_link is None

    # "href" of wong type
    link_data = {"href": 137, "type": "application/zarr"}
    ctx = new_ctx(
        job_results=JobResults(**{"a": link_data}),
    )
    assert ctx.output_link is None


def test_output_description():
    ctx = new_ctx(outputs=["a"], output_name=None)
    assert isinstance(ctx.output_description, OutputDescription)
    assert ctx.output_description.title == "The a value"
    ctx = new_ctx(outputs=["a", "b"], output_name="a")
    assert isinstance(ctx.output_description, OutputDescription)
    assert ctx.output_description.title == "The a value"
    ctx = new_ctx(outputs=["a", "b"], output_name="b")
    assert isinstance(ctx.output_description, OutputDescription)
    assert ctx.output_description.title == "The b value"
    ctx = new_ctx(outputs=["a", "b"], output_name="c")
    assert ctx.output_description is None
    ctx = new_ctx(outputs=["a", "b"], output_name=None)
    assert ctx.output_description.title == "The a value"
    ctx = new_ctx(outputs=["a", "b"], output_name=None, process_description=None)
    assert ctx.output_description is None


def test_schema_does_not_select_another_output():
    ctx = new_ctx(job_results=JobResults(root={"b": 1}), outputs=["a"])
    assert ctx.output_name == "b"
    assert ctx.output_description is None


def test_selected_value_is_independent_of_original_outputs():
    results = JobResults(root={"a": {"nested": [1]}, "b": None})
    ctx = new_ctx(job_results=results, output_name="a")
    ctx.value["nested"].append(2)
    assert results.root == {"a": {"nested": [1]}, "b": None}
    results.root["a"] = "different"
    assert ctx.output_value == {"nested": [1, 2]}


@pytest.mark.parametrize("value", [None, False, 0, 2.5, [1, None], {"a": [1]}])
def test_direct_target_has_no_required_job_facts(value):
    ctx = JobResultOpenContext(config=ClientConfig(), value=value)
    assert ctx.value is value
    assert ctx.output_value is value
    assert ctx.job_id is None
    assert ctx.job_results is None
    assert ctx.output_name is None
    assert ctx.output_description is None


def test_missing_target_is_an_error():
    with pytest.raises(JobResultOpenError, match="No selected value or job results"):
        JobResultOpenContext(config=ClientConfig())


@pytest.mark.parametrize(
    "value,location,media_type",
    [
        ("out.nc", "out.nc", None),
        (Path("out.nc"), "out.nc", None),
        ({"url": "out.nc"}, "out.nc", None),
        ({"path": 137}, None, None),
        (
            {"href": "out.nc", "type": "application/netcdf"},
            "out.nc",
            "application/netcdf",
        ),
        (qualified_value, "file://./test.zarr", "application/zarr"),
        (qualified_value.model_dump(), "file://./test.zarr", "application/zarr"),
        (
            QualifiedValue(
                mediaType="application/json",
                value={"href": "out.nc", "type": "application/netcdf"},
            ),
            "out.nc",
            "application/json",
        ),
        (
            QualifiedValue(mediaType="application/json", value={"a": 1}),
            None,
            "application/json",
        ),
    ],
)
def test_effective_location_and_media_type(value, location, media_type):
    ctx = JobResultOpenContext(config=ClientConfig(), value=value)
    assert ctx.location == location
    assert ctx.output_media_type == media_type


def test_explicit_location_and_media_type_override_without_mutation():
    ctx = JobResultOpenContext(
        config=ClientConfig(),
        value=link_value,
        location="replacement.tif",
        _media_type="image/tiff; application=geotiff",
    )
    assert ctx.location == "replacement.tif"
    assert ctx.output_media_type == "image/tiff; application=geotiff"
    assert link_value.href == "file://./test.tif"
    assert link_value.type == "application/cog"


def test_model_location():
    class PathValue(BaseModel):
        path: str

    ctx = JobResultOpenContext(config=ClientConfig(), value=PathValue(path="out.nc"))
    assert ctx.location == "out.nc"
