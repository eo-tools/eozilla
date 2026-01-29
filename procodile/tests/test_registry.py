#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
import unittest

from procodile import (
    FromMain,
    Process,
    ProcessRegistry,
    Workflow,
    WorkflowStepRegistry,
)

from .test_process import f1, f2, f3, f4, f4_fail_ctx


class TestProcessRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ProcessRegistry()

        @self.registry.main(
            id="first_step",
            inputs={"id": None},
            outputs={"a": None},
        )
        def first_step(id: str) -> str:
            return id

        @first_step.step(
            id="second_step",
            inputs={"id": FromMain(output="a")},
        )
        def second_step(id: str) -> str:
            return id

        self.first_step = first_step
        self.second_step = second_step

    def test_len_and_contains(self):
        self.assertEqual(len(self.registry), 1)
        self.assertIn("first_step", self.registry)
        self.assertNotIn("missing", self.registry)

    def test_getitem_returns_process(self):
        proc = self.registry["first_step"]

        self.assertIsInstance(proc, Process)
        self.assertEqual(proc.description.id, "first_step")

    def test_get_method(self):
        proc = self.registry.get("first_step")
        missing = self.registry.get("missing")

        self.assertIsInstance(proc, Process)
        self.assertIsNone(missing)

    def test_get_workflows(self):
        wfs = self.registry.workflows()

        self.assertIsInstance(wfs, dict)
        self.assertEqual(next(iter(wfs.keys())), "first_step")
        self.assertIsInstance(next(iter(wfs.values())).registry, WorkflowStepRegistry)
        self.assertIsInstance(
            next(iter(wfs.values())).registry.main["first_step"], Process
        )
        self.assertIsInstance(
            next(iter(wfs.values())).registry.steps["second_step"]["step"], Process
        )
        self.assertEqual(
            next(iter(wfs.values())).registry.steps["second_step"]["dependencies"],
            {"id": {"output": "a", "type": "from_main"}},
        )

    def test_iteration_yields_keys(self):
        keys = list(self.registry)
        self.assertEqual(keys, ["first_step"])

    def test_values_yield_processes(self):
        values = list(self.registry.values())

        self.assertEqual(len(values), 1)
        self.assertIsInstance(values[0], Process)

    def test_items_yield_id_and_process(self):
        items = list(self.registry.items())

        self.assertEqual(len(items), 1)
        workflow_id, proc = items[0]

        self.assertEqual(workflow_id, "first_step")
        self.assertIsInstance(proc, Process)

    def test_get_workflow_returns_workflow(self):
        wf = self.registry.get_workflow("first_step")

        self.assertIsInstance(wf, Workflow)
        self.assertEqual(wf.id, "first_step")

    def test_workflow_without_steps_returns_main_interface(self):
        registry = ProcessRegistry()

        @registry.process(id="main")
        def main(x: int) -> int:
            return x

        proc = registry["main"]

        self.assertIsInstance(proc, Process)
        self.assertEqual(proc.description.id, "main")
        self.assertEqual(proc.function, main.run)

    def test_registry_never_returns_workflow(self):
        for value in self.registry.values():
            self.assertNotIsInstance(value, Workflow)
            self.assertIsInstance(value, Process)

        for _, value in self.registry.items():
            self.assertNotIsInstance(value, Workflow)
            self.assertIsInstance(value, Process)

    def test_register(self):
        registry = ProcessRegistry()

        self.assertEqual(None, registry.get("f1"))
        self.assertEqual([], list(registry.keys()))

        # use as no-arg decorator
        registry.process(f1)
        self.assertEqual(1, len(registry))
        p1 = list(registry.values())[0]
        self.assertIsInstance(p1, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertEqual(["tests.test_process:f1"], list(registry.keys()))

        # use as decorator with args
        registry.process(id="f2")(f2)
        self.assertEqual(2, len(registry))
        p1, p2 = registry.values()
        self.assertIsInstance(p1, Process)
        self.assertIsInstance(p2, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertIs(p2, registry.get(p2.description.id))
        self.assertEqual(["tests.test_process:f1", "f2"], list(registry.keys()))

        # use as function
        registry.process(f3, id="my_fn3")
        self.assertEqual(3, len(registry))
        p1, p2, p3 = registry.values()
        self.assertIsInstance(p1, Process)
        self.assertIsInstance(p2, Process)
        self.assertIsInstance(p3, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertIs(p2, registry.get(p2.description.id))
        self.assertIs(p3, registry.get(p3.description.id))
        self.assertEqual(
            ["tests.test_process:f1", "f2", "my_fn3"], list(registry.keys())
        )

        # use JobContext
        registry.process(f4, id="func4_with_job_ctx")
        self.assertEqual(4, len(registry))
        p1, p2, p3, p4 = registry.values()
        self.assertIsInstance(p1, Process)
        self.assertIsInstance(p2, Process)
        self.assertIsInstance(p3, Process)
        self.assertIsInstance(p4, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertIs(p2, registry.get(p2.description.id))
        self.assertIs(p3, registry.get(p3.description.id))
        self.assertIs(p4, registry.get(p4.description.id))
        self.assertEqual(
            ["tests.test_process:f1", "f2", "my_fn3", "func4_with_job_ctx"],
            list(registry.keys()),
        )

        # use 2 JobContext
        with self.assertRaises(ValueError):
            registry.process(f4_fail_ctx, id="f4_fail_ctx_with_2_job_ctx")
        self.assertEqual(4, len(registry))

        with self.assertRaises(KeyError):
            _ = registry["f4_fail_ctx_with_2_job_ctx"]

        self.assertEqual(
            ["tests.test_process:f1", "f2", "my_fn3", "func4_with_job_ctx"],
            list(registry.keys()),
        )
