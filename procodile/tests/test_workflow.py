import unittest
from typing import Annotated

from procodile import (
    FromMain,
    FromStep,
    Process,
    WorkflowRegistry,
    WorkflowStepRegistry,
)
from procodile.workflow import FINAL_STEP_ID, extract_dependency


class TestDependencyHelpers(unittest.TestCase):
    def test_extract_dependency_from_annotated_from_main(self):
        ann = Annotated[int, FromMain("result")]
        dep = extract_dependency(ann)
        self.assertEqual(dep, {"output": "result", "type": "from_main"})

    def test_extract_dependency_from_annotated_from_step(self):
        ann = Annotated[int, FromStep("step_a", "result")]
        dep = extract_dependency(ann)
        self.assertEqual(
            dep, {"step_id": "step_a", "output": "result", "type": "from_step"}
        )

    def test_extract_dependency_none(self):
        self.assertIsNone(extract_dependency(int))
        self.assertIsNone(extract_dependency(None))


class TestDependencyGraph(unittest.TestCase):
    def setUp(self):
        self.registry = WorkflowRegistry()
        self.workflow = self.registry.get_or_create_workflow("wf")

    def test_linear_dependency_graph(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main(x: int) -> int:
            return x + 1

        @self.workflow.step(id="step1")
        def step1(a: Annotated[int, FromMain("a")]) -> int:
            return a * 2

        @self.workflow.step(id="step2")
        def step2(b: Annotated[int, FromStep("step1", "return_value")]) -> int:
            return b + 3

        order, graph = self.workflow.execution_order

        self.assertEqual(order, ["main", "step1", "step2", FINAL_STEP_ID])

        self.assertEqual(graph["main"], {"step1"})
        self.assertEqual(graph["step1"], {"step2"})
        self.assertEqual(graph["step2"], {FINAL_STEP_ID})
        self.assertNotIn(FINAL_STEP_ID, graph)

    def test_unknown_step_dependency_raises(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(x: Annotated[int, FromStep("missing_step", "return_value")]) -> int:
            return x

        with self.assertRaises(ValueError) as ctx:
            self.workflow.execution_order

        self.assertIn("depends on unknown step", str(ctx.exception))

    def test_invalid_main_output_dependency_raises(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(x: Annotated[int, FromMain("missing_output")]) -> int:
            return x

        with self.assertRaises(ValueError) as ctx:
            self.workflow.execution_order

        self.assertIn("expects output", str(ctx.exception))

    def test_cycle_detection(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(x: Annotated[int, FromStep("step2", "return_value")]) -> int:
            return x

        @self.workflow.step(id="step2")
        def step2(y: Annotated[int, FromStep("step1", "return_value")]) -> int:
            return y

        with self.assertRaises(ValueError) as ctx:
            self.workflow.execution_order

        self.assertIn("cycle", str(ctx.exception))

    def test_multiple_leaf_nodes_raises(self):
        @self.workflow.main(id="main", outputs={"a": None})
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(x: Annotated[int, FromMain("a")]) -> int:
            return x + 1

        @self.workflow.step(id="step2")
        def step2(x: Annotated[int, FromMain("a")]) -> int:
            return x + 2

        with self.assertRaises(ValueError):
            self.workflow.execution_order


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
        def step1(x: Annotated[int, FromMain("out")]) -> int:
            return x * 2

        @self.workflow.step(
            id="step2",
            outputs={"final": None},
        )
        def step2(y: Annotated[int, FromStep("step1", "double")]) -> int:
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

        # step1 is connected to main but still has a missing argument `x` which is
        # not connected to any step.
        @self.workflow.step(id="step1")
        def step1(
            x: int,
            _unused: Annotated[int, FromMain("out")],
        ) -> int:
            return x

        @self.workflow.step(id="step2")
        def step2(y: Annotated[int, FromStep("step1", "return_value")]) -> int:
            return y

        with self.assertRaises(ValueError) as ctx:
            self.workflow.run()

        self.assertIn("Missing required argument", str(ctx.exception))

    def test_visualize_workflow(self):
        @self.workflow.main(id="main")
        def main() -> int:
            return 1

        @self.workflow.step(id="step1")
        def step1(x: Annotated[int, FromMain("return_value")]) -> int:
            return x

        dot = self.workflow.visualize_workflow()

        self.assertIn("digraph pipeline", dot)
        self.assertIn('"main" -> "step1"', dot)

    def test_workflow_with_default_args(self):
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
            x: Annotated[int, FromMain("out")],
            factor: int = 2,  # DEFAULT ARG
        ) -> int:
            return x * factor

        @self.workflow.step(
            id="step2",
            outputs={"final": None},
        )
        def step2(y: Annotated[int, FromStep("step1", "double")]) -> int:
            return y + 1

        outputs = self.workflow.run(a=2, b=3)

        self.assertEqual(outputs["final"], 11)

    def test_workflow__as_process_cache(self):
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
            x: Annotated[int, FromMain("out")],
            factor: int = 2,  # DEFAULT ARG
        ) -> int:
            return x * factor

        @self.workflow.step(
            id="step2",
            outputs={"final": None},
        )
        def step2(y: Annotated[int, FromStep("step1", "double")]) -> int:
            return y + 1

        self.registry._as_process.cache_clear()

        process = self.registry._as_process(self.workflow)

        self.assertIsInstance(process, Process)

        process2 = self.registry._as_process(self.workflow)

        assert process is process2

        second_workflow = self.registry.get_or_create_workflow("second_workflow")

        @second_workflow.main(
            id="main",
            outputs={"out": None},
        )
        def main_new(a: int, b: int) -> int:
            return a + b

        @second_workflow.step(
            id="step1",
            outputs={"double": None},
        )
        def step1_new(
            x: Annotated[int, FromMain("out")],
            factor: int = 2,  # DEFAULT ARG
        ) -> int:
            return x * factor

        @second_workflow.step(
            id="step2",
            outputs={"final": None},
        )
        def step2_new(y: Annotated[int, FromStep("step1", "double")]) -> int:
            return y + 1

        process3 = self.registry._as_process(second_workflow)
        assert process3 is not process2
        assert process3 is not process


class TestWorkflowStepRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = WorkflowStepRegistry()

    def test_register_main_stores_process(self):
        def main(x: int) -> int:
            return x + 1

        self.registry.register_main(main, id="main")

        self.assertIn("main", self.registry.main)
        process = self.registry.main["main"]
        self.assertEqual(process.description.id, "main")

    def test_register_step_without_dependencies(self):
        def step1(x: int, y: int) -> int:
            return x + y

        self.registry.register_step(step1, id="step1")

        self.assertIn("step1", self.registry.steps)
        entry = self.registry.steps["step1"]

        self.assertEqual(entry["dependencies"], {})
        self.assertEqual(
            list(entry["step"].description.inputs.keys()),
            ["x", "y"],
        )

    def test_dependency_from_main_via_annotated(self):
        def step1(x: Annotated[int, FromMain("a")]) -> int:
            return x

        self.registry.register_step(step1, id="step1")

        entry = self.registry.steps["step1"]

        self.assertEqual(
            entry["dependencies"],
            {"x": {"type": "from_main", "output": "a"}},
        )
        self.assertEqual(list(entry["step"].description.inputs.keys()), ["x"])

    def test_dependency_from_step_via_annotated(self):
        def step1() -> int:
            return 1

        def step2(x: Annotated[int, FromStep("step1", "return_value")]) -> int:
            return x

        self.registry.register_step(step1, id="step1")
        self.registry.register_step(step2, id="step2")

        entry = self.registry.steps["step2"]

        self.assertEqual(
            entry["dependencies"],
            {
                "x": {
                    "type": "from_step",
                    "step_id": "step1",
                    "output": "return_value",
                }
            },
        )

    def test_dependency_from_inputs_kwarg(self):
        def step1(x: int) -> int:
            return x

        self.registry.register_step(
            step1,
            id="step1",
            inputs={"x": FromMain("a")},
        )

        entry = self.registry.steps["step1"]

        self.assertEqual(
            entry["dependencies"],
            {"x": {"type": "from_main", "output": "a"}},
        )

    def test_schema_input_from_inputs_kwarg(self):
        def step1(x: int) -> int:
            return x

        self.registry.register_step(
            step1,
            id="step1",
            inputs={"x": FromMain("b")},
        )

        entry = self.registry.steps["step1"]

        self.assertEqual(
            entry["dependencies"], {"x": {"output": "b", "type": "from_main"}}
        )
        self.assertEqual(list(entry["step"].description.inputs.keys()), ["x"])

    def test_annotated_and_inputs_merge(self):
        def step1(
            x: Annotated[int, FromMain("a")],
            y: int,
        ) -> int:
            return x + y

        self.registry.register_step(
            step1,
            id="step1",
            inputs={"y": FromMain("b")},
        )

        entry = self.registry.steps["step1"]

        self.assertEqual(
            entry["dependencies"],
            {
                "x": {"type": "from_main", "output": "a"},
                "y": {"type": "from_main", "output": "b"},
            },
        )
        self.assertEqual(
            list(entry["step"].description.inputs.keys()),
            ["x", "y"],
        )

    def test_duplicate_dependency_definition_raises(self):
        def step1(x: Annotated[int, FromMain("b")]) -> int:
            return x

        with self.assertRaises(ValueError) as ctx:
            self.registry.register_step(
                step1,
                id="step1",
                inputs={"x": FromMain("a")},
            )

        self.assertEqual(
            "Duplicate dependency definition for input 'x'",
            str(ctx.exception),
        )

    def test_invalid_dependency_metadata_raises(self):
        class DummyMeta:
            pass

        def step1(x: Annotated[int, DummyMeta()]) -> int:
            return x

        with self.assertRaises(ValueError):
            self.registry.register_step(step1, id="step1")
