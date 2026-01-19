from appligator.airflow.handlers.base_handler import OperatorHandler
from appligator.airflow.models import TaskIR


class KubernetesOperatorHandler(OperatorHandler):
    """
    OperatorHandler implementation for tasks executed inside Kubernetes pods.

    This handler renders TaskIR objects with runtime="kubernetes" into
    KubernetesPodOperator definitions. Task execution is delegated to
    `run_step.main`, which resolves and invokes the target function inside
    the container.
    """

    def supports(self, task: TaskIR) -> bool:
        return task.runtime == "kubernetes"

    def render(self, task: TaskIR) -> str:
        from appligator.airflow.renderer import render_task_inputs
        inputs = render_task_inputs(task.inputs)

        return f"""
    tasks["{task.id}"] = KubernetesPodOperator(
        task_id="{task.id}",
        image="{task.image}",
        cmds=["python", "/app/run_step.py"],
        arguments=[json.dumps({{
            "func_module": "{task.func_module}",
            "func_qualname": "{task.func_qualname}",
            "inputs": {{{inputs}}},
            "output_keys": {task.outputs},
        }})],
        do_xcom_push=True,
    )
"""
