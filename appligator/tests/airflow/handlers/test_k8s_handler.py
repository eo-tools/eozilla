import unittest

from appligator.airflow.handlers.k8s_handler import KubernetesOperatorHandler
from appligator.airflow.models import TaskIR


class TestKubernetesOperatorHandler(unittest.TestCase):
    def setUp(self):
        self.handler = KubernetesOperatorHandler()

    def test_supports_kubernetes(self):
        task = TaskIR(id="t", runtime="kubernetes", inputs={})
        self.assertTrue(self.handler.supports(task))

    def test_does_not_support_other_runtimes(self):
        task = TaskIR(id="t", runtime="syn-python", inputs={})
        self.assertFalse(self.handler.supports(task))

    def test_full_render_output(self):
        task = TaskIR(
            id="main",
            runtime="kubernetes",
            func_module="my.module",
            func_qualname="my_func",
            image="my-image",
            inputs={"x": "param:x", "y": "xcom:second_step:y"},
            outputs=["out"],
            depends_on=[],
        )

        rendered = self.handler.render(task)

        expected = """
    tasks["main"] = KubernetesPodOperator(
        task_id="main",
        image="my-image",
        cmds=["python", "/app/run_step.py"],
        arguments=[json.dumps({
            "func_module": "my.module",
            "func_qualname": "my_func",
            "inputs": {"x": "{{ params.x }}",
"y": "{{ ti.xcom_pull(task_ids=\'second_step\')[\'y\'] }}"},
            "output_keys": [\'out\'],
        })],
        do_xcom_push=True,
    )
"""
        self.assertEqual(
            expected,
            rendered,
        )
