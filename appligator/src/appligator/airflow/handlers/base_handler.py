from appligator.airflow.models import TaskIR


class OperatorHandler:
    """
    Base interface for rendering a TaskIR (Task Intermediate Representation) into an
    Airflow operator definition.

    An OperatorHandler is responsible for:
    - Declaring whether it can handle a given TaskIR (via `supports`)
    - Rendering the task into Airflow DAG source code (via `render`)

    Handlers must be:
    - Stateless
    - Backend-specific (Airflow)
    - Task-scoped (must not depend on WorkflowIR)

    The renderer selects the first handler whose `supports()` method returns True.
    """

    def supports(self, task: TaskIR) -> bool:
        """
        Return True if this handler can render the given task.

        Args:
            task: A TaskIR describing an executable workflow task.

        Returns:
            True if this handler supports the task's runtime, otherwise False.
        """
        raise NotImplementedError

    def render(self, task: TaskIR) -> str:
        """
        Render the given task as a Python code snippet inside an Airflow DAG.

        Args:
            task: A TaskIR instance to render.

        Returns:
            A string containing valid Python code that defines an Airflow operator.
        """
        raise NotImplementedError
