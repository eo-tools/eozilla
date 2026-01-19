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
        cmd = [
            "python",
            "-c",
            f"\"from run_step import main; main("
            f"func_module='{task.func_module}', "
            f"func_qualname='{task.func_qualname}', "
            f"inputs={{{inputs}}}, "
            f"output_keys={task.outputs}"
            f")\"",
        ]


        return f"""
    tasks["{task.id}"] = KubernetesPodOperator(
        task_id="{task.id}",
        image="{task.image}",
        cmds={cmd},
        do_xcom_push=True,
    )
"""
