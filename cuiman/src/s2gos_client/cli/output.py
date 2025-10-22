#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Literal

import pydantic
import typer

from s2gos_common.models import (
    JobInfo,
    JobList,
    JobResults,
    ProcessDescription,
    ProcessList,
)
from s2gos_common.process.request import ExecutionRequest


class OutputFormat(str, Enum):
    simple = "simple"
    json = "json"
    yaml = "yaml"


def output(message: str):
    typer.echo(message)


def get_renderer(
    output_format: OutputFormat, verbose: bool = False
) -> "OutputRenderer":
    renderers: dict[OutputFormat, Callable[[bool], OutputRenderer]] = {
        OutputFormat.simple: SimpleOutputRenderer,
        OutputFormat.json: JsonOutputRenderer,
        OutputFormat.yaml: YamlOutputRenderer,
    }
    return renderers[output_format](verbose)


class OutputRenderer(ABC):
    @abstractmethod
    def render_process_list(self, process_list: ProcessList) -> str:
        """Render a process list."""

    @abstractmethod
    def render_process_description(
        self, process_description: ProcessDescription
    ) -> str:
        """Render a process description."""

    @abstractmethod
    def render_execution_request_valid(
        self, execution_request: ExecutionRequest
    ) -> str:
        """Render an execution request is valid."""

    @abstractmethod
    def render_job_list(self, job_list: JobList) -> str:
        """Render a job list."""

    @abstractmethod
    def render_job_info(self, job: JobInfo) -> str:
        """Render a job."""

    @abstractmethod
    def render_job_results(self, job_results: JobResults) -> str:
        """Render a job results."""

    def _render_base_model(
        self,
        base_model: pydantic.BaseModel,
        format_name: Literal["json", "yaml"] = "yaml",
    ) -> str:
        serialized_value = self._serialize_model(base_model)
        if format_name == "yaml":
            import yaml

            text_value = yaml.safe_dump(serialized_value, indent=2)
        else:
            import json

            text_value = json.dumps(serialized_value, indent=2)
        return text_value

    @classmethod
    def _serialize_model(cls, base_model: pydantic.BaseModel) -> Any:
        return base_model.model_dump(
            mode="json",
            by_alias=True,
            exclude_defaults=True,
            exclude_none=True,
            exclude_unset=True,
        )


class SimpleOutputRenderer(OutputRenderer):
    def __init__(self, verbose: bool):
        self.verbose = verbose

    def render_process_list(self, process_list: ProcessList) -> str:
        if not process_list.processes:
            return "No processes available."
        else:
            return "\n".join(
                f"{i + 1}: {process.id} - {process.title}"
                for i, process in enumerate(process_list.processes)
            )

    def render_process_description(
        self, process_description: ProcessDescription
    ) -> str:
        return self._render_base_model(process_description)

    def render_execution_request_valid(
        self, execution_request: ExecutionRequest
    ) -> str:
        return "Execution request is valid:\n" + self._render_base_model(
            execution_request
        )

    def render_job_list(self, job_list: JobList) -> str:
        if not job_list.jobs:
            return "No jobs available."
        else:
            return "\n".join(
                f"{i + 1}: {job.jobID} - {job.status} - {job.progress} - {job.message}"
                for i, job in enumerate(job_list.jobs)
            )

    def render_job_info(self, job: JobInfo) -> str:
        return "\n".join(
            [
                f"Job ID:      {job.jobID}",
                f"Process ID:  {job.processID}",
                f"Status:      {job.status}",
                f"Progress:    {job.progress}",
                f"Message:     {job.message}",
                f"Created at:  {job.created}",
                f"Started at:  {job.started}",
                f"Updated at:  {job.updated}",
                f"Ended at:    {job.finished}",
            ]
        )

    def render_job_results(self, job_results: JobResults) -> str:
        return self._render_base_model(job_results)


class StructuredOutputRenderer(OutputRenderer):
    def __init__(self, format_name: Literal["json", "yaml"], verbose: bool):
        self.format_name = format_name
        self.verbose = verbose

    def render_process_list(self, process_list: ProcessList) -> str:
        return self._render_base_model(process_list, self.format_name)

    def render_process_description(
        self, process_description: ProcessDescription
    ) -> str:
        return self._render_base_model(process_description, self.format_name)

    def render_execution_request_valid(
        self, execution_request: ExecutionRequest
    ) -> str:
        return self._render_base_model(execution_request, self.format_name)

    def render_job_list(self, job_list: JobList) -> str:
        return self._render_base_model(job_list, self.format_name)

    def render_job_info(self, job: JobInfo) -> str:
        return self._render_base_model(job, self.format_name)

    def render_job_results(self, job_results: JobResults) -> str:
        return self._render_base_model(job_results, self.format_name)


class YamlOutputRenderer(StructuredOutputRenderer):
    def __init__(self, verbose: bool):
        super().__init__("yaml", verbose)


class JsonOutputRenderer(StructuredOutputRenderer):
    def __init__(self, verbose: bool):
        super().__init__("json", verbose)
