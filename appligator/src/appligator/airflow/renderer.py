#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from datetime import datetime, timedelta

from appligator.airflow.handlers.k8s_handler import KubernetesOperatorHandler
from appligator.airflow.handlers.syn_python_handler import (
    SyntheticPythonsOperatorHandler,
)
from appligator.airflow.models import TaskIR, Toleration, WorkflowIR

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

        needs_k8s = any(
            t.env_from_secrets
            or t.resources
            or t.pvc_mounts
            or t.config_map_mounts
            or t.node_selector
            or t.tolerations
            for t in workflow.tasks
        )
        lines.extend(render_header(needs_k8s=needs_k8s))

        shared_config = render_k8s_shared_config(workflow)
        if shared_config:
            lines.append(shared_config)

        lines.append(render_dag_open(workflow))

        for task in workflow.tasks:
            lines.append(self.render_task(task))

        for task in workflow.tasks:
            for upstream in task.depends_on or []:
                lines.append(f'{TAB}tasks["{upstream}"] >> tasks["{task.id}"]')

        lines.append("\n")

        return "\n".join(lines)

    def render_task(self, task: TaskIR) -> str:
        for handler in self.handlers:
            if handler.supports(task):
                return handler.render(task)
        raise ValueError(f"No operator adapter for task {task.id}")


def render_k8s_shared_config(workflow: WorkflowIR) -> str | None:
    node_selector = next(
        (t.node_selector for t in workflow.tasks if t.node_selector), None
    )
    tolerations = next((t.tolerations for t in workflow.tasks if t.tolerations), None)

    if not node_selector and not tolerations:
        return None

    lines = ["# ── Shared Kubernetes config ───────────────────────────────────"]

    if node_selector:
        lines.append(f"_node_selector = {node_selector!r}")
        lines.append("")

    if tolerations:
        tol_items = [_render_toleration(t) for t in tolerations]
        lines.append("_tolerations = [")
        for i, item in enumerate(tol_items):
            sep = "," if i < len(tol_items) - 1 else ""
            lines.append(f"{item}{sep}")
        lines.append("]")
        lines.append("")

    return "\n".join(lines)


def _render_toleration(t: Toleration) -> str:
    args = ["    k8s.V1Toleration("]
    args.append(f"        key={t.key!r},")
    args.append(f"        operator={t.operator!r},")
    if t.value is not None:
        args.append(f"        value={t.value!r},")
    if t.effect is not None:
        args.append(f"        effect={t.effect!r},")
    if t.toleration_seconds is not None:
        args.append(f"        toleration_seconds={t.toleration_seconds},")
    args.append("    )")
    return "\n".join(args)


def render_header(needs_k8s: bool = False) -> list[str]:
    lines = [
        "import json",
        "from datetime import datetime",
        "\nfrom airflow import DAG",
        "from airflow.models.param import Param",
        "from airflow.providers.standard.operators.python import PythonOperator",
        "from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator",
    ]
    if needs_k8s:
        lines.append("from kubernetes.client import models as k8s")
    lines.append("")
    return lines


def render_dag_open(workflow: WorkflowIR) -> str:
    params_block = render_dag_params(workflow.params)
    start_date = (datetime.now() - timedelta(days=1)).date().isoformat()
    return f"""
with DAG(
    dag_id="{workflow.id}",
    start_date=datetime.fromisoformat("{start_date}"),
    schedule=None,
    catchup=False,
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
