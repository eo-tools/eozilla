#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase
from unittest.mock import patch

import httpx

from cuiman.api.client import Client
from cuiman.api.openers import (
    JobResultOpenerRegistry,
    OpenJobResultContext,
    build_open_job_result_context,
    infer_data_type,
)
from gavicore.models import (
    InlineOrRefValue,
    InlineValue,
    JobResults,
    Link,
    OutputDescription,
    ProcessDescription,
    QualifiedValue,
    Schema,
)

from ..helpers import MockTransport


class OpenersTest(TestCase):
    def setUp(self):
        self.client = Client(api_url="https://acme.ogc.org/api", _transport=MockTransport())

    def test_infer_data_type_variants(self):
        process_description = ProcessDescription(
            id="p1",
            version="1.0",
            outputs={"result": OutputDescription(schema=Schema(format="netcdf"))},
        )
        self.assertEqual(
            "forced",
            infer_data_type(None, output_entry=None, process_description=None, output_name=None, options={"data_type": "forced"}),
        )
        self.assertEqual(
            "json",
            infer_data_type(
                Link(href="https://x", type="application/json"),
                output_entry=None,
                process_description=None,
                output_name=None,
                options={},
            ),
        )
        self.assertEqual(
            "text",
            infer_data_type("x", output_entry=None, process_description=None, output_name=None, options={"media_type": "text/plain"}),
        )
        self.assertEqual(
            "netcdf",
            infer_data_type("x", output_entry=None, process_description=None, output_name=None, options={"media_type": "application/x-netcdf"}),
        )
        self.assertEqual(
            "geotiff",
            infer_data_type("x", output_entry=None, process_description=None, output_name=None, options={"media_type": "image/tiff"}),
        )
        self.assertEqual(
            "netcdf",
            infer_data_type("uri", output_entry=None, process_description=process_description, output_name="result", options={}),
        )
        self.assertEqual("json", infer_data_type({"a": 1}, output_entry=None, process_description=None, output_name=None, options={}))
        self.assertEqual("text", infer_data_type("abc", output_entry=None, process_description=None, output_name=None, options={}))
        self.assertEqual("bytes", infer_data_type(b"abc", output_entry=None, process_description=None, output_name=None, options={}))
        self.assertEqual("link", infer_data_type(Link(href="https://x"), output_entry=None, process_description=None, output_name=None, options={}))
        self.assertEqual("raw", infer_data_type(123, output_entry=None, process_description=None, output_name=None, options={}))

    def test_context_building_for_output_selection_and_inline_value(self):
        context = build_open_job_result_context(
            client=self.client,
            job_results=JobResults(root={"result": InlineOrRefValue(root=InlineValue(root={"x": 1}))}),
            data_type=None,
            process_description=None,
            options={},
        )
        self.assertEqual("result", context.output_name)
        self.assertEqual({"x": 1}, context.output_value)

        context2 = build_open_job_result_context(
            client=self.client,
            job_results=JobResults(root={"a": InlineOrRefValue(root=1), "b": InlineOrRefValue(root=2)}),
            data_type=None,
            process_description=None,
            options={"output_name": "b"},
        )
        self.assertEqual("b", context2.output_name)
        self.assertEqual(2, context2.output_value)

    def test_context_media_type_properties(self):
        link_context = build_open_job_result_context(
            client=self.client,
            job_results=JobResults(root={"result": InlineOrRefValue(root=Link(href="https://x", type="application/json"))}),
            data_type=None,
            process_description=None,
            options={},
        )
        self.assertEqual("application/json", link_context.media_type)
        self.assertIsNotNone(link_context.output_link)

        qualified_context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value=QualifiedValue(mediaType="application/x-netcdf", value=InlineValue(root="u")),
            output_entry=None,
            process_description=None,
            data_type="raw",
            options={},
        )
        self.assertEqual("application/x-netcdf", qualified_context.media_type)

        options_context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value=42,
            output_entry=None,
            process_description=None,
            data_type="raw",
            options={"media_type": "text/plain"},
        )
        self.assertEqual("text/plain", options_context.media_type)
        self.assertIsNone(options_context.output_link)

    def test_registry_fallback_matcher_and_missing(self):
        registry = JobResultOpenerRegistry.create_default()
        context = build_open_job_result_context(
            client=self.client,
            job_results=JobResults(root={"result": InlineOrRefValue(root={"x": 1})}),
            data_type="not-registered",
            process_description=None,
            options={},
        )
        self.assertEqual({"x": 1}, registry.open(context))

        registry2 = JobResultOpenerRegistry.create_default()
        registry2.register_matcher("is-dict", lambda c: isinstance(c.output_value, dict), lambda c: "matched")
        self.assertEqual("matched", registry2.open(context))

        registry3 = JobResultOpenerRegistry()
        with self.assertRaises(ValueError):
            registry3.open(context)

    def test_default_openers_non_link(self):
        registry = JobResultOpenerRegistry.create_default()
        text_context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value=7,
            output_entry=None,
            process_description=None,
            data_type="text",
            options={},
        )
        self.assertEqual("7", registry.open(text_context))

        bytes_context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value="abc",
            output_entry=None,
            process_description=None,
            data_type="bytes",
            options={},
        )
        self.assertEqual(b"abc", registry.open(bytes_context))

        link_context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value=Link(href="https://x"),
            output_entry=None,
            process_description=None,
            data_type="link",
            options={},
        )
        self.assertEqual("https://x", registry.open(link_context))

    def test_default_openers_link_fetch(self):
        registry = JobResultOpenerRegistry.create_default()
        context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value=Link(href="https://example.org/data", type="application/json"),
            output_entry=None,
            process_description=None,
            data_type="json",
            options={"headers": {"X-Test": "1"}, "timeout": 12.0},
        )

        request = httpx.Request("GET", "https://example.org/data")
        response_json = httpx.Response(200, request=request, json={"ok": True})
        response_text = httpx.Response(200, request=request, text="hello")
        response_bytes = httpx.Response(200, request=request, content=b"abc")

        with patch("cuiman.api.openers.httpx.get", return_value=response_json) as mocked_get:
            self.assertEqual({"ok": True}, registry.open(context))
            kwargs = mocked_get.call_args.kwargs
            self.assertEqual(12.0, kwargs["timeout"])
            self.assertIn("X-Test", kwargs["headers"])

        text_context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value=Link(href="https://example.org/data"),
            output_entry=None,
            process_description=None,
            data_type="text",
            options={},
        )
        with patch("cuiman.api.openers.httpx.get", return_value=response_text):
            self.assertEqual("hello", registry.open(text_context))

        bytes_context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value=Link(href="https://example.org/data"),
            output_entry=None,
            process_description=None,
            data_type="bytes",
            options={},
        )
        with patch("cuiman.api.openers.httpx.get", return_value=response_bytes):
            self.assertEqual(b"abc", registry.open(bytes_context))

        bad_context = OpenJobResultContext(
            client=self.client,
            job_results=JobResults(root={}),
            output_name=None,
            output_value="not-link",
            output_entry=None,
            process_description=None,
            data_type="json",
            options={},
        )
        # json opener on non-link returns the raw value
        self.assertEqual("not-link", registry.open(bad_context))
