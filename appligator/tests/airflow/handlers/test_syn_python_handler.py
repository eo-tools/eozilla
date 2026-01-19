import unittest

from appligator.airflow.handlers.syn_python_handler import (
    SyntheticPythonsOperatorHandler,
)
from appligator.airflow.models import TaskIR


class TestSyntheticPythonsOperatorHandler(unittest.TestCase):
    """
    Tests SyntheticPythonsOperatorHandler behavior and output.
    """

    def setUp(self):
        self.handler = SyntheticPythonsOperatorHandler()

    def test_supports_syn_python(self):
        task = TaskIR(
            id="final",
            runtime="syn-python",
            inputs={"upstream_task_id": "xcom_task:step"},
            depends_on=["step"],
        )
        self.assertTrue(self.handler.supports(task))

    def test_does_not_support_kubernetes(self):
        task = TaskIR(id="t", runtime="kubernetes", inputs={})
        self.assertFalse(self.handler.supports(task))

    def test_full_render_output(self):
        task = TaskIR(
            id="__procodile_final_step__",
            runtime="syn-python",
            inputs={"upstream_task_id": "prev_step"},
            depends_on=["prev_step"],
        )

        rendered = self.handler.render(task)

        expected = """
    def _final_step_callable(ti, upstream_task_id):
        return ti.xcom_pull(task_ids=upstream_task_id)
    
    tasks["__procodile_final_step__"] = PythonOperator(
        task_id="__procodile_final_step__",
        python_callable=_final_step_callable,
        op_kwargs={
            "upstream_task_id": "prev_step"
        },
        do_xcom_push=True
    )
"""

        self.assertEqual(
            rendered,
            expected,
        )
