from abc import ABC, abstractmethod
from typing import Any

from s2gos_common.models import ProcessDescription
from s2gos_common.process import ExecutionRequest


# noinspection PyShadowingBuiltins
class ClientMixin(ABC):
    """
    Extra methods for the API client (synchronous mode).
    """

    @abstractmethod
    def get_process(self, process_id: str, **kwargs: Any) -> ProcessDescription:
        """Will be overridden by the actual client class."""

    def create_execution_request(
        self,
        process_id: str,
        dotpath: bool = False,
    ) -> ExecutionRequest:
        """
        Create a template for an execution request
        generated from the process description of the
        given process identifier.

        Args:
            process_id: The process identifier
            dotpath: Whether to create dot-separated input
                names for nested object values

        Returns:
            The execution request template.

        Raises:
            ClientError: if an error occurs
        """
        process_description = self.get_process(process_id)
        return ExecutionRequest.from_process_description(
            process_description, dotpath=dotpath
        )
