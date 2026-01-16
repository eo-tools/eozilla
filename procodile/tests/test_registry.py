#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
import unittest

from procodile import Process, WorkflowRegistry, Workflow, FromMain

from .test_process import f1, f2, f3, f4, f4_fail_ctx


class TestWorkflowRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = WorkflowRegistry()
        wf = self.registry.get_or_create_workflow("first_workflow")

        @wf.main(
            id="first_step",
            inputs={"id": None},
            outputs={"a": None},
        )
        def first_step(id: str) -> str:
            return id

        @wf.step(
            id="second_step",
            inputs={"id": FromMain(output="a")},
        )
        def second_step(id: str) -> str:
            return id

    def test_get_or_create_workflow(self):
        registry = WorkflowRegistry()

        wf1 = registry.get_or_create_workflow("wf")
        wf2 = registry.get_or_create_workflow("wf")

        self.assertIs(wf1, wf2)
        self.assertEqual(len(registry), 1)
        self.assertIn("wf", list(registry))

    def test_len_and_contains(self):
        self.assertEqual(len(self.registry), 1)
        self.assertIn("first_workflow", self.registry)
        self.assertNotIn("missing", self.registry)

    def test_getitem_returns_process(self):
        proc = self.registry["first_workflow"]

        self.assertIsInstance(proc, Process)
        self.assertEqual(proc.description.id, "first_workflow")

    def test_get_method(self):
        proc = self.registry.get("first_workflow")
        missing = self.registry.get("missing")

        self.assertIsInstance(proc, Process)
        self.assertIsNone(missing)

    def test_iteration_yields_keys(self):
        keys = list(self.registry)
        self.assertEqual(keys, ["first_workflow"])

    def test_values_yield_processes(self):
        values = list(self.registry.values())

        self.assertEqual(len(values), 1)
        self.assertIsInstance(values[0], Process)

    def test_items_yield_id_and_process(self):
        items = list(self.registry.items())

        self.assertEqual(len(items), 1)
        workflow_id, proc = items[0]

        self.assertEqual(workflow_id, "first_workflow")
        self.assertIsInstance(proc, Process)

    def test_get_workflow_returns_workflow(self):
        wf = self.registry.get_workflow("first_workflow")

        self.assertIsInstance(wf, Workflow)
        self.assertEqual(wf.id, "first_workflow")

    def test_workflow_without_steps_returns_main_interface(self):
        registry = WorkflowRegistry()
        wf = registry.get_or_create_workflow("simple")

        @wf.main(id="main")
        def main(x: int) -> int:
            return x

        proc = registry["simple"]

        self.assertIsInstance(proc, Process)
        self.assertEqual(proc.description.id, "simple")
        self.assertEqual(proc.function, wf.run)

    def test_multiple_main_steps_raises(self):
        registry = WorkflowRegistry()
        wf = registry.get_or_create_workflow("bad")

        @wf.main(id="a")
        def a(x: int) -> int:
            return x

        @wf.main(id="b")
        def b(x: int) -> int:
            return x

        with self.assertRaises(ValueError):
            _ = registry["bad"]

    def test_registry_never_returns_workflow(self):
        for value in self.registry.values():
            self.assertNotIsInstance(value, Workflow)
            self.assertIsInstance(value, Process)

        for _, value in self.registry.items():
            self.assertNotIsInstance(value, Workflow)
            self.assertIsInstance(value, Process)

    def test_register(self):
        registry = WorkflowRegistry()

        self.assertEqual(None, registry.get("f1"))
        self.assertEqual([], list(registry.keys()))

        # use as no-arg decorator
        workflow = registry.get_or_create_workflow("workflow")
        workflow.main(f1)
        self.assertEqual(1, len(registry))
        p1 = list(registry.values())[0]
        self.assertIsInstance(p1, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertEqual(["workflow"], list(registry.keys()))

        # use as decorator with args
        workflow2 = registry.get_or_create_workflow("workflow2")
        workflow2.main(id="f2")(f2)
        self.assertEqual(2, len(registry))
        p1, p2 = registry.values()
        self.assertIsInstance(p1, Process)
        self.assertIsInstance(p2, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertIs(p2, registry.get(p2.description.id))
        self.assertEqual(["workflow", "workflow2"], list(registry.keys()))

        # use as function
        workflow3 = registry.get_or_create_workflow("workflow3")
        workflow3.main(f3, id="my_fn3")
        self.assertEqual(3, len(registry))
        p1, p2, p3 = registry.values()
        self.assertIsInstance(p1, Process)
        self.assertIsInstance(p2, Process)
        self.assertIsInstance(p3, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertIs(p2, registry.get(p2.description.id))
        self.assertIs(p3, registry.get(p3.description.id))
        self.assertEqual(["workflow", "workflow2", "workflow3"], list(registry.keys()))

        # use JobContext
        workflow4 = registry.get_or_create_workflow("workflow4")
        workflow4.main(f4, id="func4_with_job_ctx")
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
            ["workflow", "workflow2", "workflow3", "workflow4"], list(registry.keys())
        )

        # use 2 JobContext
        workflow5 = registry.get_or_create_workflow("workflow5")
        with self.assertRaises(ValueError):
            workflow5.main(f4_fail_ctx, id="f4_fail_ctx_with_2_job_ctx")
        self.assertEqual(5, len(registry))

        with self.assertRaises(ValueError):
            _ = registry["workflow5"]

        self.assertEqual(
            ["workflow", "workflow2", "workflow3", "workflow4", "workflow5"],
            list(registry.keys())
        )
