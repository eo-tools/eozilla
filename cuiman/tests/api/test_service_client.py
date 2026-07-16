#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase

from cuiman.api.jobs import JobOptions
from cuiman.api.service_client import (
    fetch_process_descriptions,
    generate_service_client_modules,
    write_service_client_modules,
)
from cuiman.api import service_client
from gavicore.models import DataType, InputDescription, ProcessDescription, Schema


def mk_process_description() -> ProcessDescription:
    return ProcessDescription(
        id="simulate-scene",
        version="1.0.0",
        title="Simulate scene",
        inputs={
            "bbox": InputDescription(
                title="Bounding box",
                schema=Schema(type=DataType.array, items=Schema(type=DataType.number)),
            ),
            "class": InputDescription(
                title="Class name",
                schema=Schema(type=DataType.string),
            ),
            "job_options": InputDescription(
                minOccurs=0,
                title="Server-side job options",
                schema=Schema(type=DataType.object),
            ),
        },
    )


class GenerateServiceClientModulesTest(TestCase):
    def test_fetch_process_descriptions(self):
        process_1 = ProcessDescription(id="one", version="1.0.0")
        process_2 = ProcessDescription(id="two", version="1.0.0")

        class FakeClient:
            def __init__(self):
                self.calls: list[str] = []

            def get_processes(self):
                return SimpleNamespace(
                    processes=[
                        SimpleNamespace(id=process_1.id),
                        SimpleNamespace(id=process_2.id),
                    ]
                )

            def get_process(self, process_id: str) -> ProcessDescription:
                self.calls.append(process_id)
                return {"one": process_1, "two": process_2}[process_id]

        client = FakeClient()

        result = fetch_process_descriptions(client)

        self.assertEqual([process_1, process_2], result)
        self.assertEqual(["one", "two"], client.calls)

    def test_write_service_client_modules(self):
        generated = generate_service_client_modules("s2gos", [mk_process_description()])

        with TemporaryDirectory() as tmp_dir:
            paths = write_service_client_modules(
                "s2gos",
                [mk_process_description()],
                output_dir=tmp_dir,
            )

            self.assertEqual(Path(tmp_dir) / "s2gos_sync.py", paths["sync"])
            self.assertEqual(Path(tmp_dir) / "s2gos_async.py", paths["async"])
            self.assertEqual(generated.sync_code, paths["sync"].read_text())
            self.assertEqual(generated.async_code, paths["async"].read_text())

    def test_generate_service_client_modules_handles_empty_method_list(self):
        generated = generate_service_client_modules("class", [])

        self.assertEqual("class__sync", generated.sync_module_name)
        self.assertEqual("ClassClient", generated.sync_class_name)
        self.assertIn("pass", generated.sync_code)
        self.assertIn("pass", generated.async_code)

    def test_generate_service_client_modules_without_inputs(self):
        generated = generate_service_client_modules(
            "demo",
            [
                ProcessDescription(
                    id="plain-process",
                    version="1.0.0",
                    title="Plain process",
                    description="This process has no inputs.",
                )
            ],
        )

        self.assertIn("Plain process", generated.sync_code)
        self.assertIn("This process has no inputs.", generated.sync_code)
        self.assertIn("job_options: JobOptions | None = None", generated.sync_code)
        self.assertIn("job_options: JobOptions | None = None", generated.async_code)

    def test_generate_service_client_modules_separates_multiple_methods(self):
        generated = generate_service_client_modules(
            "demo",
            [
                ProcessDescription(id="first", version="1.0.0"),
                ProcessDescription(id="second", version="1.0.0"),
            ],
        )

        self.assertIn(
            f"{2 * service_client.TAB})\n\n{service_client.TAB}def second(",
            generated.sync_code,
        )

    def test_generated_method_has_clean_docstring(self):
        process = ProcessDescription(
            id='say-"""-hello',
            version="1.0.0",
            title='A """quoted""" title\non two lines',
            description="First description line\nsecond description line",
            inputs={
                "message": InputDescription(
                    description='Say """hello"""\nover two lines',
                    schema=Schema(type=DataType.string),
                ),
                "fallback": InputDescription(schema=Schema(type=DataType.integer)),
            },
        )
        generated = generate_service_client_modules("demo", [process])
        namespace: dict[str, object] = {}

        exec(generated.sync_code, namespace)  # noqa: S102

        method = namespace["DemoClient"].say_hello
        self.assertEqual(
            inspect.cleandoc(
                '''
                Execute process ``say-"""-hello`` and return its opened result.

                A """quoted""" title
                on two lines

                First description line
                second description line

                Args:
                    message: Say """hello""" over two lines
                    fallback: Process input.
                    job_options: Optional job execution and result-opening options.

                Raises:
                    ClientError: If the API call, job execution, or result opening fails.
                '''
            ),
            inspect.getdoc(method),
        )
        self.assertIn(
            f'{2 * service_client.TAB}"""Execute process',
            generated.sync_code,
        )
        self.assertFalse(
            any(line.endswith(" ") for line in generated.sync_code.splitlines())
        )

    def test_sync_client_class_executes_generated_method(self):
        generated = generate_service_client_modules("s2gos", [mk_process_description()])
        self.assertEqual("s2gos_sync", generated.sync_module_name)
        self.assertEqual("S2gosClient", generated.sync_class_name)
        namespace: dict[str, object] = {}
        exec(generated.sync_code, namespace)  # noqa: S102
        calls = []

        def fake_helper(self, process_id, request, *, job_options=None):
            calls.append((self, process_id, request, job_options))
            return "opened"

        namespace["execute_and_open_result"] = fake_helper
        client_cls = namespace["S2gosClient"]
        client = client_cls(api_url="https://acme.ogc.org/api")
        options = JobOptions(timeout=1)
        result = client.simulate_scene(
            bbox=[1.0, 2.0, 3.0, 4.0],
            class_="snow",
            job_options_=None,
            job_options=options,
        )
        self.assertEqual("opened", result)
        _, process_id, request, job_options = calls[0]
        self.assertEqual("simulate-scene", process_id)
        self.assertEqual(
            {"bbox": [1.0, 2.0, 3.0, 4.0], "class": "snow"},
            request.inputs,
        )
        self.assertIs(options, job_options)

    def test_private_helper_branches(self):
        self.assertEqual("class_", service_client._to_identifier("class"))
        self.assertEqual("_123_value", service_client._to_identifier("123 value"))
        self.assertEqual("value", service_client._to_identifier("!!!"))

        self.assertEqual("name", service_client._unique_identifier("name", set()))
        self.assertEqual(
            "name_",
            service_client._unique_identifier("name", {"name"}),
        )
        self.assertEqual(
            "name_2",
            service_client._unique_identifier("name", {"name", "name_"}),
        )
        self.assertEqual(
            "name_3",
            service_client._unique_identifier("name", {"name", "name_", "name_2"}),
        )

        self.assertEqual("Service", service_client._to_pascal_case("!!!"))
        self.assertEqual(
            "FooBar",
            service_client._to_pascal_case("foo bar"),
        )
        self.assertEqual(
            "multi line text",
            service_client._clean_doc_line("  multi\nline\ttext  "),
        )

        self.assertEqual(
            "Any",
            service_client._get_base_type_hint(None),
        )
        self.assertEqual(
            "bool",
            service_client._get_base_type_hint(Schema(type=DataType.boolean)),
        )
        self.assertEqual(
            "int",
            service_client._get_base_type_hint(Schema(type=DataType.integer)),
        )
        self.assertEqual(
            "float",
            service_client._get_base_type_hint(Schema(type=DataType.number)),
        )
        self.assertEqual(
            "str",
            service_client._get_base_type_hint(Schema(type=DataType.string)),
        )
        self.assertEqual(
            "list[int]",
            service_client._get_base_type_hint(
                Schema(type=DataType.array, items=Schema(type=DataType.integer))
            ),
        )
        self.assertEqual(
            "dict[str, Any]",
            service_client._get_base_type_hint(Schema(type=DataType.object)),
        )
        self.assertEqual(
            "Any",
            service_client._get_base_type_hint(SimpleNamespace(type="custom")),
        )

        default_schema = Schema(type=DataType.string, default="alpha")
        default_input = InputDescription(schema=default_schema)
        self.assertEqual(
            ("'alpha'", False), service_client._get_default_code(default_input)
        )

        optional_input = InputDescription(
            minOccurs=0,
            schema=Schema(type=DataType.integer),
        )
        self.assertEqual(
            ("None", True), service_client._get_default_code(optional_input)
        )
        self.assertEqual(
            "int | None",
            service_client._get_type_hint(optional_input.schema_, include_none=True),
        )
        self.assertEqual(
            True,
            service_client._is_nullable(
                InputDescription(schema=Schema(type=DataType.string, nullable=True))
            ),
        )


class GenerateAsyncServiceClientModulesTest(IsolatedAsyncioTestCase):
    async def test_async_client_class_executes_generated_method(self):
        generated = generate_service_client_modules("s2gos", [mk_process_description()])
        self.assertEqual("s2gos_async", generated.async_module_name)
        self.assertEqual("S2gosAsyncClient", generated.async_class_name)
        namespace: dict[str, object] = {}
        exec(generated.async_code, namespace)  # noqa: S102
        calls = []

        async def fake_helper(self, process_id, request, *, job_options=None):
            calls.append((self, process_id, request, job_options))
            return "opened"

        namespace["async_execute_and_open_result"] = fake_helper
        client_cls = namespace["S2gosAsyncClient"]
        client = client_cls(api_url="https://acme.ogc.org/api")
        result = await client.simulate_scene(
            bbox=[1.0, 2.0, 3.0, 4.0],
            class_="snow",
        )
        self.assertEqual("opened", result)
        _, process_id, request, job_options = calls[0]
        self.assertEqual("simulate-scene", process_id)
        self.assertEqual(
            {"bbox": [1.0, 2.0, 3.0, 4.0], "class": "snow"},
            request.inputs,
        )
        self.assertIsNone(job_options)
