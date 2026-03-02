#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from cuiman.api.openers import JobResultOpenerRegistry, build_open_job_result_context, infer_data_type
from gavicore.models import (
    InlineOrRefValue,
    JobResults,
    Link,
    OutputDescription,
    ProcessDescription,
    Schema,
)

from ..helpers import MockTransport
from cuiman.api.client import Client


class OpenersTest(TestCase):
    def setUp(self):
        self.client = Client(api_url="https://acme.ogc.org/api", _transport=MockTransport())

    def test_infer_data_type_from_media_type(self):
        output_entry = InlineOrRefValue(root=Link(href="https://example.org/x.json", type="application/json"))
        data_type = infer_data_type(
            output_entry.root,
            output_entry=output_entry,
            process_description=None,
            output_name="result",
            options={},
        )
        self.assertEqual("json", data_type)

    def test_infer_data_type_from_output_schema_format(self):
        process_description = ProcessDescription(
            id="p1",
            version="1.0",
            outputs={
                "result": OutputDescription(schema=Schema(format="netcdf")),
            },
        )
        data_type = infer_data_type(
            output_value="https://example.org/out.nc",
            output_entry=None,
            process_description=process_description,
            output_name="result",
            options={},
        )
        self.assertEqual("netcdf", data_type)

    def test_opener_registry_fallback_to_raw(self):
        registry = JobResultOpenerRegistry.create_default()
        context = build_open_job_result_context(
            client=self.client,
            job_results=JobResults(root={"result": InlineOrRefValue(root={"x": 1})}),
            data_type="not-registered",
            process_description=None,
            options={},
        )
        result = registry.open(context)
        self.assertEqual({"x": 1}, result)

    def test_opener_registry_custom_data_type(self):
        registry = JobResultOpenerRegistry.create_default()
        registry.register_data_type("netcdf", lambda context: ("opened", context.output_value))
        context = build_open_job_result_context(
            client=self.client,
            job_results=JobResults(root={"result": InlineOrRefValue(root="s3://bucket/file.nc")}),
            data_type="netcdf",
            process_description=None,
            options={},
        )
        result = registry.open(context)
        self.assertEqual(("opened", "s3://bucket/file.nc"), result)
