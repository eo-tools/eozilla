from datetime import datetime, timedelta

from appligator.airflow.handlers.k8s_handler import KubernetesOperatorHandler
from appligator.airflow.handlers.syn_python_handler import (
    SyntheticPythonsOperatorHandler)
from appligator.airflow.models import TaskIR, WorkflowIR

INDENT = "            "
TAB = "    "

class AirflowRenderer:
    """
    Render a WorkflowIR into an Airflow DAG Python source file.

    OperatorHandlers encapsulate operator-specific rendering logic, while
    the renderer orchestrates workflow-level structure.
    """

    def __init__(self):
        self.handlers = [
            KubernetesOperatorHandler(),
            SyntheticPythonsOperatorHandler(),
        ]

    def render(self, workflow: WorkflowIR) -> str:
        """
        Render the entire workflow as a Python DAG file.

        Args:
            workflow: A WorkflowIR instance.

        Returns:
            A string containing the full Airflow DAG source code.
        """
        lines: list[str] = []

        lines.extend(render_header())

        lines.append(render_dag_open(workflow))

        for task in workflow.tasks:
            lines.append(self.render_task(task))

        for task in workflow.tasks:
            for upstream in task.depends_on:
                lines.append(f'{TAB}tasks["{upstream}"] >> tasks["{task.id}"]')

        lines.append("\n")

        return "\n".join(lines)

    def render_task(self, task: TaskIR) -> str:
        for handler in self.handlers:
            if handler.supports(task):
                return handler.render(task)
        raise ValueError(f"No operator adapter for task {task.id}")

def render_header() -> list[str]:
    return [
        "from datetime import datetime",
        "\nfrom airflow import DAG",
        "from airflow.models.param import Param",
        "from airflow.providers.standard.operators.python import PythonOperator",
        "from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator",
        "",
    ]

def render_dag_open(workflow: WorkflowIR) -> str:
    params_block = render_dag_params(workflow.params)
    start_date = (datetime.now() - timedelta(days=1)).date().isoformat()
    return f"""
with DAG(
    dag_id="{workflow.id}",
    start_date=datetime.fromisoformat("{start_date}"),
    schedule=None,
    catchup=False,
    render_template_as_native_obj=True,
    is_paused_upon_creation=False,
    params={{
{params_block}
    }},
) as dag:

    tasks = {{}}
"""


def render_dag_params(params: dict[str, dict]) -> str:
    lines = []

    for name, schema in params.items():
        args = ", ".join(f"{k}={v!r}" for k, v in schema.items())
        lines.append(f'{TAB}"{name}": Param({args})')

    return ",\n".join(lines)

def render_task_inputs(inputs: dict[str, str]) -> str:
    lines: list[str] = []

    for name, value in inputs.items():
        if value.startswith("param:"):
            param_name = value.removeprefix("param:")
            expr = f"{{{{ params.{param_name} }}}}"

        elif value.startswith("xcom:"):
            _, task_id, output_key = value.split(":", 2)
            expr = f"{{{{ ti.xcom_pull(task_ids='{task_id}')['{output_key}'] }}}}"

        else:
            raise ValueError(f"Unknown input reference: {value}")

        lines.append(f'"{name}": "{expr}"')

    return ",\n".join(lines)
