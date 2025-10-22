#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from s2gos_client.cli.output import OutputFormat, OutputRenderer, get_renderer
from s2gos_common.models import (
    JobInfo,
    JobList,
    JobResults,
    JobStatus,
    JobType,
    ProcessDescription,
    ProcessList,
    ProcessSummary,
)
from s2gos_common.process.request import ExecutionRequest


class OutputTest(TestCase):
    def test_simple(self):
        outputs = get_outputs(get_renderer(OutputFormat.simple))
        self.assertEqual(
            {
                "render_job": (
                    "Job ID:      job_8\n"
                    "Process ID:  primes_between\n"
                    "Status:      JobStatus.running\n"
                    "Progress:    None\n"
                    "Message:     None\n"
                    "Created at:  None\n"
                    "Started at:  None\n"
                    "Updated at:  None\n"
                    "Ended at:    None"
                ),
                "render_job_list": "1: job_8 - JobStatus.running - None - None",
                "render_job_list_empty": "No jobs available.",
                "render_job_results": (
                    "return_value:\n- 2\n- 3\n- 5\n- 7\n- 11\n- 13\n"
                ),
                "render_process_description": (
                    "id: primes_between\n"
                    "inputs:\n"
                    "  max_val:\n"
                    "    schema:\n"
                    "      type: integer\n"
                    "    title: Maximum value\n"
                    "  min_val:\n"
                    "    schema:\n"
                    "      type: integer\n"
                    "    title: Minimum value\n"
                    "version: 1.4.0\n"
                ),
                "render_process_list": "1: primes_between - None",
                "render_process_list_empty": "No processes available.",
                "render_execution_request_valid": (
                    "Execution request is valid:\n"
                    "inputs:\n"
                    "  max_val: 20\n"
                    "  min_val: 0\n"
                    "process_id: primes_between\n"
                ),
            },
            outputs,
        )

    def test_yaml(self):
        outputs = get_outputs(get_renderer(OutputFormat.yaml))
        self.assertEqual(
            {
                "render_job": (
                    "jobID: job_8\n"
                    "processID: primes_between\n"
                    "status: running\n"
                    "type: process\n"
                ),
                "render_job_list": (
                    "jobs:\n"
                    "- jobID: job_8\n"
                    "  processID: primes_between\n"
                    "  status: running\n"
                    "  type: process\n"
                    "links: []\n"
                ),
                "render_job_list_empty": "jobs: []\nlinks: []\n",
                "render_job_results": (
                    "return_value:\n- 2\n- 3\n- 5\n- 7\n- 11\n- 13\n"
                ),
                "render_process_description": (
                    "id: primes_between\n"
                    "inputs:\n"
                    "  max_val:\n"
                    "    schema:\n"
                    "      type: integer\n"
                    "    title: Maximum value\n"
                    "  min_val:\n"
                    "    schema:\n"
                    "      type: integer\n"
                    "    title: Minimum value\n"
                    "version: 1.4.0\n"
                ),
                "render_process_list": (
                    "links: []\nprocesses:\n- id: primes_between\n  version: 1.4.0\n"
                ),
                "render_process_list_empty": "links: []\nprocesses: []\n",
                "render_execution_request_valid": (
                    "inputs:\n  max_val: 20\n  min_val: 0\nprocess_id: primes_between\n"
                ),
            },
            outputs,
        )

    def test_json(self):
        outputs = get_outputs(get_renderer(OutputFormat.json))
        self.assertEqual(
            {
                "render_job": (
                    "{\n"
                    '  "processID": "primes_between",\n'
                    '  "type": "process",\n'
                    '  "jobID": "job_8",\n'
                    '  "status": "running"\n'
                    "}"
                ),
                "render_job_list": (
                    "{\n"
                    '  "jobs": [\n'
                    "    {\n"
                    '      "processID": "primes_between",\n'
                    '      "type": "process",\n'
                    '      "jobID": "job_8",\n'
                    '      "status": "running"\n'
                    "    }\n"
                    "  ],\n"
                    '  "links": []\n'
                    "}"
                ),
                "render_job_list_empty": '{\n  "jobs": [],\n  "links": []\n}',
                "render_job_results": (
                    "{\n"
                    '  "return_value": [\n'
                    "    2,\n"
                    "    3,\n"
                    "    5,\n"
                    "    7,\n"
                    "    11,\n"
                    "    13\n"
                    "  ]\n"
                    "}"
                ),
                "render_process_description": (
                    "{\n"
                    '  "id": "primes_between",\n'
                    '  "version": "1.4.0",\n'
                    '  "inputs": {\n'
                    '    "min_val": {\n'
                    '      "title": "Minimum value",\n'
                    '      "schema": {\n'
                    '        "type": "integer"\n'
                    "      }\n"
                    "    },\n"
                    '    "max_val": {\n'
                    '      "title": "Maximum value",\n'
                    '      "schema": {\n'
                    '        "type": "integer"\n'
                    "      }\n"
                    "    }\n"
                    "  }\n"
                    "}"
                ),
                "render_process_list": (
                    "{\n"
                    '  "processes": [\n'
                    "    {\n"
                    '      "id": "primes_between",\n'
                    '      "version": "1.4.0"\n'
                    "    }\n"
                    "  ],\n"
                    '  "links": []\n'
                    "}"
                ),
                "render_process_list_empty": '{\n  "processes": [],\n  "links": []\n}',
                "render_execution_request_valid": (
                    "{\n"
                    '  "inputs": {\n'
                    '    "min_val": 0,\n'
                    '    "max_val": 20\n'
                    "  },\n"
                    '  "process_id": "primes_between"\n'
                    "}"
                ),
            },
            outputs,
        )


def get_outputs(renderer: OutputRenderer) -> dict[str, str]:
    return {
        "render_process_list": renderer.render_process_list(
            ProcessList(
                processes=[ProcessSummary(id="primes_between", version="1.4.0")],
                links=[],
            )
        ),
        "render_process_list_empty": renderer.render_process_list(
            ProcessList(
                processes=[],
                links=[],
            )
        ),
        "render_process_description": renderer.render_process_description(
            ProcessDescription(
                id="primes_between",
                version="1.4.0",
                inputs={
                    "min_val": {
                        "title": "Minimum value",
                        "schema": {"type": "integer"},
                    },
                    "max_val": {
                        "title": "Maximum value",
                        "schema": {"type": "integer"},
                    },
                },
            ),
        ),
        "render_execution_request_valid": renderer.render_execution_request_valid(
            ExecutionRequest(
                process_id="primes_between", inputs={"min_val": 0, "max_val": 20}
            )
        ),
        "render_job_list": renderer.render_job_list(
            JobList(
                jobs=[
                    JobInfo(
                        processID="primes_between",
                        jobID="job_8",
                        type=JobType.process,
                        status=JobStatus.running,
                    )
                ],
                links=[],
            )
        ),
        "render_job_list_empty": renderer.render_job_list(
            JobList(
                jobs=[],
                links=[],
            )
        ),
        "render_job": renderer.render_job_info(
            JobInfo(
                processID="primes_between",
                jobID="job_8",
                type=JobType.process,
                status=JobStatus.running,
            )
        ),
        "render_job_results": renderer.render_job_results(
            JobResults(**{"return_value": [2, 3, 5, 7, 11, 13]})
        ),
    }
