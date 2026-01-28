import unittest

from appligator.airflow.handlers.base_handler import OperatorHandler
from appligator.airflow.models import TaskIR, WorkflowIR
from appligator.airflow.renderer import (
    AirflowRenderer,
    render_dag_open,
    render_dag_params,
    render_header,
    render_task_inputs,
)


class TestRenderHeader(unittest.TestCase):
    def test_render_header_contains_expected_imports(self):
        header = render_header()

        self.assertIn("\nfrom airflow import DAG", header)
        self.assertIn("from airflow.models.param import Param", header)
        self.assertIn("import json", header)


class TestRenderDagParams(unittest.TestCase):
    def test_render_dag_params(self):
        params = {
            "id": {"default": "abc", "type": "string"},
            "count": {"default": 3, "type": "integer"},
        }

        result = render_dag_params(params)

        self.assertIn("\"id\": Param(default='abc', type='string')", result)
        self.assertIn("\"count\": Param(default=3, type='integer')", result)


class TestRenderDagOpen(unittest.TestCase):
    def test_render_dag_open(self):
        workflow = WorkflowIR(
            id="test_dag",
            tasks=[],
            params={},
            final_task="last_step",
        )

        result = render_dag_open(workflow)

        self.assertIn('dag_id="test_dag"', result)
        self.assertIn("with DAG(", result)
        self.assertIn("tasks = {}", result)


class TestRenderTaskInputs(unittest.TestCase):
    def test_param_input(self):
        result = render_task_inputs({"x": "param:id"})
        self.assertEqual(result, '"x": "{{ params.id }}"')

    def test_xcom_input(self):
        result = render_task_inputs({"y": "xcom:task1:out"})
        self.assertEqual(
            result,
            "\"y\": \"{{ ti.xcom_pull(task_ids='task1')['out'] }}\"",
        )

    def test_invalid_input_raises(self):
        with self.assertRaises(ValueError):
            render_task_inputs({"z": "bad:value"})


class DummyHandler(OperatorHandler):
    def supports(self, task):
        return task.runtime == "kubernetes"

    def render(self, task):
        return f'    tasks["{task.id}"] = "TASK({task.id})"'


class NoSupportHandler:
    def supports(self, task):
        return False


class TestAirflowRenderer(unittest.TestCase):
    def test_render_workflow_with_dependencies(self):
        renderer = AirflowRenderer()
        renderer.handlers = [DummyHandler()]  # override real handlers

        task_a = TaskIR(id="a", inputs={}, depends_on=None, runtime="kubernetes")
        task_b = TaskIR(id="b", inputs={}, depends_on=["a"], runtime="kubernetes")

        workflow = WorkflowIR(
            id="test_workflow", tasks=[task_a, task_b], params={}, final_task="b"
        )

        result = renderer.render(workflow)

        self.assertIn('tasks["a"] = "TASK(a)"', result)
        self.assertIn('tasks["b"] = "TASK(b)"', result)
        self.assertIn('tasks["a"] >> tasks["b"]', result)

    def test_render_task_without_handler_raises(self):
        renderer = AirflowRenderer()
        renderer.handlers = [NoSupportHandler()]

        task = TaskIR(id="x", inputs={}, depends_on=None, runtime="kubernetes")

        with self.assertRaises(ValueError):
            renderer.render_task(task)

    def test_render_with_nonexistent_handler_raises(self):
        renderer = AirflowRenderer()
        renderer.handlers = []

        task = TaskIR(id="x", inputs={}, depends_on=None, runtime="kubernetes")

        with self.assertRaises(ValueError):
            renderer.render_task(task)
