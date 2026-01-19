import unittest

from appligator.airflow.ir import workflow_to_ir
from gavicore.models import Field
from procodile import Workflow
from procodile.workflow import FINAL_STEP_ID, FromMain


class TestWorkflowToIR(unittest.TestCase):
    def setUp(self):
        wf = Workflow(id="wf")

        @wf.main(
            id="main",
            inputs={"x": Field(default=1)},
            outputs={"out": Field()},
        )
        def main(x: int) -> int:
            return x

        @wf.step(
            id="step",
            inputs={"y": FromMain(output="out")},
        )
        def step(y: int) -> int:
            return y

        self.registry = wf.registry

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
