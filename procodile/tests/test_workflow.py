import unittest
from typing import Annotated

from procodile import (
    FromMain,
    FromStep,
    WorkflowRegistry,
)
from procodile.workflow import extract_dependency


class TestDependencyHelpers(unittest.TestCase):
    def test_extract_dependency_from_annotated_from_main(self):
        ann = Annotated[int, FromMain("result")]
        dep = extract_dependency(ann)
        print("dep", dep)
        self.assertIsInstance(dep, FromMain)
        self.assertEqual(dep.output, "result")

    def test_extract_dependency_from_annotated_from_step(self):
        ann = Annotated[int, FromStep("step_a", "result")]
        dep = extract_dependency(ann)

        self.assertIsInstance(dep, FromStep)
        self.assertEqual(dep.output, "result")

    def test_extract_dependency_none(self):
        self.assertIsNone(extract_dependency(int))
        self.assertIsNone(extract_dependency(None))


class TestWorkflowRegistry(unittest.TestCase):
    def test_get_or_create_workflow(self):
        registry = WorkflowRegistry()

        wf1 = registry.get_or_create_workflow("wf")
        wf2 = registry.get_or_create_workflow("wf")

        self.assertIs(wf1, wf2)
        self.assertEqual(len(registry), 1)
        self.assertIn("wf", list(registry))


class TestDependencyGraph(unittest.TestCase):
    def setUp(self):
        self.registry = WorkflowRegistry()
        self.workflow = self.registry.get_or_create_workflow("wf")

    def test_linear_dependency_graph(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main(x: int) -> int:
            return x + 1

        @self.workflow.step(id="step1")
        def step1(
            a: Annotated[int, FromMain("a")]
        ) -> int:
            return a * 2

        @self.workflow.step(id="step2")
        def step2(
            b: Annotated[int, FromStep("step1", "return_value")]
        ) -> int:
            return b + 3

        order, graph = self.workflow.execution_order

        self.assertEqual(order, ["main", "step1", "step2"])

        self.assertEqual(graph["main"], {"step1"})
        self.assertEqual(graph["step1"], {"step2"})
        self.assertNotIn("step2", graph)

    def test_unknown_step_dependency_raises(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(
            x: Annotated[int, FromStep("missing_step", "return_value")]
        ) -> int:
            return x

        with self.assertRaises(ValueError) as ctx:
            self.workflow.execution_order

        self.assertIn("depends on unknown step", str(ctx.exception))

    def test_invalid_main_output_dependency_raises(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(
            x: Annotated[int, FromMain("missing_output")]
        ) -> int:
            return x

        with self.assertRaises(ValueError) as ctx:
            self.workflow.execution_order

        self.assertIn("expects output", str(ctx.exception))

    def test_cycle_detection(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(
            x: Annotated[int, FromStep("step2", "return_value")]
        ) -> int:
            return x

        @self.workflow.step(id="step2")
        def step2(
            y: Annotated[int, FromStep("step1", "return_value")]
        ) -> int:
            return y

        with self.assertRaises(ValueError) as ctx:
            self.workflow.execution_order

        self.assertIn("cycle", str(ctx.exception))

class TestWorkflowEndToEnd(unittest.TestCase):
    def setUp(self):
        self.registry = WorkflowRegistry()
        self.workflow = self.registry.get_or_create_workflow("test_workflow")

    def test_workflow_with_main_and_steps(self):
        @self.workflow.main(
            id="main",
            outputs={"out": None},
        )
        def main(a: int, b: int) -> int:
            return a + b

        @self.workflow.step(
            id="step1",
            outputs={"double": None},
        )
        def step1(
            x: Annotated[int, FromMain("out")]
        ) -> int:
            return x * 2

        @self.workflow.step(
            id="step2",
            outputs={"final": None},
        )
        def step2(
            y: Annotated[int, FromStep("step1", "double")]
        ) -> int:
            return y + 1

        outputs = self.workflow.run(a=2, b=3)

        self.assertEqual(outputs["final"], 11)

    def test_missing_required_argument_raises(self):
        @self.workflow.main(
            id="main",
            outputs={"out": None},
        )
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(x: int) -> int:
            return x

        with self.assertRaises(ValueError) as ctx:
            self.workflow.run()

        self.assertIn("Missing required argument", str(ctx.exception))

    def test_visualize_workflow(self):
        @self.workflow.main(id="main")
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(
            x: Annotated[int, FromMain("return_value")]
        ) -> int:
            return x

        dot = self.workflow.visualize_workflow()

        self.assertIn("digraph pipeline", dot)
        self.assertIn('"main" -> "step1"', dot)
