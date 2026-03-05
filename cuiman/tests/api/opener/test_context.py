from dataclasses import replace
from typing import Any

from cuiman import ClientConfig
from cuiman.api.opener import JobResultOpenContext
from gavicore.models import (
    InlineValue,
    JobResults,
    Link,
    OutputDescription,
    ProcessDescription,
    QualifiedValue,
    Schema,
)

DEFAULT_JOB_RESULTS = {"a": "out.nc", "b": 2.5, "c": True}


def new_ctx(
    job_results: JobResults | None = None,
    data_type: type | None = None,
    output_name: str | None = None,
    outputs: list[str] | None = None,
    process_description: ProcessDescription | None = None,
    **options: Any,
) -> JobResultOpenContext:
    return JobResultOpenContext(
        config=ClientConfig(api_url="http://localhost:9090"),
        job_id="982a04ee",
        job_results=job_results if job_results is not None else DEFAULT_JOB_RESULTS,
        process_description=(
            process_description
            if process_description is not None
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
        data_type=data_type,
        output_name=output_name,
        options=options,
    )


qualified_value = QualifiedValue(
    mediaType="application/zarr", value=InlineValue(root="file://./test.zarr")
)
link_value = Link(type="application/cog", href="file://./test.tif")
inline_value = InlineValue(root="file://./test.nc")

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


def test_output_value_yields_none():
    assert replace(ctx_qualified_2, job_results=JobResults()).output_value is None
    assert replace(ctx_qualified_2, output_name=None).output_value is None
    assert replace(ctx_link_2, output_name=None).output_value is None
    assert replace(ctx_inline_2, output_name=None).output_value is None


def test_output_media_type():
    assert ctx_qualified_1.output_media_type == "application/zarr"
    assert ctx_link_1.output_media_type == "application/cog"
    assert ctx_inline_1.output_media_type is None


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
        job_results=JobResults(**{"a": InlineValue(root=link_data)}),
    )
    assert ctx.output_link == Link(**link_data)

    # missing "href"
    link_data = {"path": "s3://xcube/test.zarr", "type": "application/zarr"}
    ctx = new_ctx(
        job_results=JobResults(**{"a": InlineValue(root=link_data)}),
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
    assert ctx.output_description is None
    ctx = new_ctx(outputs=["a", "b"], output_name=None, process_description=None)
    assert ctx.output_description is None
