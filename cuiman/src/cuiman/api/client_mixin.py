#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any

from gavicore.models import InputDescription, ProcessDescription
from gavicore.util.request import ExecutionRequest


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

    # noinspection PyUnusedLocal
    @classmethod
    def accept_process(
        cls, process_description: ProcessDescription, **filter_kwargs: Any
    ) -> bool:
        """
        Predicate function that is used to filter the list of processes.
        The function is intended to be overridden by subclasses in order to allow
        for evaluating the given `process_description` in an application-specific way.
        This includes the using custom fields in the given
        [ProcessDescription][gavicore.models.ProcessDescription] instance.

        Applications may use the [extend_model()][gavicore.util.model.extend_model]
        function to enhance existing model classes by their custom fields.

        The default implementation unconditionally returns `True`.

        Args:
            process_description: A process description.
            filter_kwargs: Implementation specific arguments passed
                by a user of this class.

        Returns:
            `True` to accept the given `process_description`, otherwise `False`.
        """
        return True

    # TODO: check if process_id should be process_description
    # TODO: pass also input_name

    # noinspection PyUnusedLocal
    @classmethod
    def accept_input(
        cls, process_id: str, input_description: InputDescription, **filter_kwargs: Any
    ) -> bool:
        """
        Predicate function that is used to filter the list of inputs of a process.
        The function is intended to be overridden by subclasses in order to allow
        for evaluating the given `input_description` in an application-specific way.
        This includes the using custom fields in the given
        [InputDescription][gavicore.models.InputDescription] instance.

        Applications may use the [extend_model()][gavicore.util.model.extend_model]
        function to enhance existing model classes by their custom fields.

        The default implementation unconditionally returns `True`.

        Args:
            process_id: The process identifier.
            input_description: An input description.
            filter_kwargs: Implementation specific arguments passed
                by a user of this class.

        Returns:
            `True` to accept the given `input_description`, otherwise `False`.
        """
        return True
