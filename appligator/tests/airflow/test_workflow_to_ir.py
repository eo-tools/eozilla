import unittest

from appligator.airflow.ir import workflow_to_ir
from gavicore.models import Field
from procodile import Workflow, ProcessRegistry
from procodile.workflow import FINAL_STEP_ID, FromMain, FromStep


class TestWorkflowToIR(unittest.TestCase):
    def setUp(self):
        registry = ProcessRegistry()

        @registry.main(
            id="main",
            inputs={"x": Field(default=1)},
            outputs={"out": Field()},
        )
        def main(x: int) -> int:
            return x

        @main.step(
            id="step",
            inputs={"y": FromMain(output="out")},
        )
        def step(y: int) -> int:
            return y

        self.registry = main.registry

    def test_ir_structure(self):
        ir = workflow_to_ir(self.registry, "wf", "img")

        self.assertEqual(ir.id, "wf")
        self.assertEqual(len(ir.tasks), 3)  # main + step + synthetic

    def test_param_extraction(self):
        ir = workflow_to_ir(self.registry, "wf")

        self.assertIn("x", ir.params)
        self.assertEqual(ir.params["x"]["default"], 1)

    def test_inputs_normalized(self):
        ir = workflow_to_ir(self.registry, "wf")

        main = next(t for t in ir.tasks if t.id == "main")
        step = next(t for t in ir.tasks if t.id == "step")

        self.assertEqual(main.inputs, {"x": "param:x"})
        self.assertEqual(step.inputs, {"y": "xcom:main:out"})

    def test_synthetic_task(self):
        ir = workflow_to_ir(self.registry, "wf")
        print(ir)
        syn = next(t for t in ir.tasks if t.id == FINAL_STEP_ID)

        self.assertEqual(syn.runtime, "syn-python")
        self.assertEqual(syn.depends_on, ["step"])

    def test_complete_ir(self):
        ir = workflow_to_ir(
            registry=self.registry,
            workflow_id="wf",
            image_name="",
        )

        expected = {
            "id": "wf",
            "params": {
                "x": {
                    "default": 1,
                    "type": "integer",
                    "title": "X",
                }
            },
            "tasks": [
                {
                    "id": "main",
                    "runtime": "kubernetes",
                    "func_module": "tests.airflow.test_workflow_to_ir",
                    "func_qualname": "TestWorkflowToIR.setUp.<locals>.main",
                    "image": "",
                    "command": None,
                    "env": None,
                    "inputs": {"x": "param:x"},
                    "outputs": ["out"],
                    "depends_on": [],
                },
                {
                    "id": "step",
                    "runtime": "kubernetes",
                    "func_module": "tests.airflow.test_workflow_to_ir",
                    "func_qualname": "TestWorkflowToIR.setUp.<locals>.step",
                    "image": "",
                    "command": None,
                    "env": None,
                    "inputs": {"y": "xcom:main:out"},
                    "outputs": ["return_value"],
                    "depends_on": ["main"],
                },
                {
                    "id": FINAL_STEP_ID,
                    "runtime": "syn-python",
                    "func_module": None,
                    "func_qualname": None,
                    "image": None,
                    "command": None,
                    "env": None,
                    "inputs": {"upstream_task_id": "step"},
                    "outputs": [],
                    "depends_on": ["step"],
                },
            ],
            "final_task": "step",
        }

        self.assertEqual(ir.model_dump(), expected)

    def test_multiple_params_extracted(self):
        registry = ProcessRegistry()

        @registry.main(
            id="main",
            inputs={
                "x": Field(default=1),
                "y": Field(default=2, title="second field"),
            },
            outputs={"out": Field()},
        )
        def main(x: int, y: int) -> int:
            return x + y

        ir = workflow_to_ir(main.registry, "wf2")

        self.assertEqual(set(ir.params.keys()), {"x", "y"})
        self.assertEqual(ir.params["x"]["default"], 1)
        self.assertEqual(ir.params["y"]["default"], 2)
        self.assertEqual(ir.params["y"]["title"], "second field")

    def test_default_output_key_used(self):
        registry = ProcessRegistry()

        @registry.main(
            id="main",
            inputs={"x": Field(default=1)},
        )
        def main(x: int) -> int:
            return x

        ir = workflow_to_ir(main.registry, "wf")

        main_ir = next(t for t in ir.tasks if t.id == "main")
        self.assertEqual(main_ir.outputs, ["return_value"])

    def test_step_to_step_dependency(self):
        registry = ProcessRegistry()

        @registry.main(
            id="main",
            inputs={"x": Field(default=1)},
            outputs={"out": Field()},
        )
        def main(x: int) -> int:
            return x

        @main.step(
            id="step1",
            inputs={"y": FromMain(output="out")},
            outputs={"z": Field()},
        )
        def step1(y: int) -> int:
            return y

        @main.step(
            id="step2",
            inputs={"w": FromStep(step_id="step1", output="z")},
        )
        def step_2(w: int) -> int:
            return w

        ir = workflow_to_ir(main.registry, "wf")

        step2 = next(t for t in ir.tasks if t.id == "step2")

        self.assertEqual(
            step2.inputs,
            {"w": "xcom:step1:z"},
        )
        self.assertEqual(step2.depends_on, ["step1"])
