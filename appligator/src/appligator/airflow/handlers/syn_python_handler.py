from appligator.airflow.handlers.base_handler import OperatorHandler
from appligator.airflow.models import TaskIR


class SyntheticPythonsOperatorHandler(OperatorHandler):
    """
    OperatorHandler for Python tasks executed via PythonOperator.

    This handler is used for internal workflow plumbing, such as the final
    synthetic task that forwards the output of the last real task under a
    stable task ID (FINAL_STEP_ID).

    These tasks are not user-defined and exist solely for workflow consistency.
    """

    def supports(self, task: TaskIR) -> bool:
        return task.runtime == "syn-python"

    def render(self, task: TaskIR) -> str:
        upstream = task.inputs["upstream_task_id"]

        return f"""
    def _final_step_callable(ti, upstream_task_id):
        return ti.xcom_pull(task_ids=upstream_task_id)
    
    tasks["{task.id}"] = PythonOperator(
        task_id="{task.id}",
        python_callable=_final_step_callable,
        op_kwargs={{
            "upstream_task_id": "{upstream}"
        }},
        do_xcom_push=True
    )
"""
