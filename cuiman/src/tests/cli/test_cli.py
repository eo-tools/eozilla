#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from unittest import TestCase

import typer.testing
from tests.helpers import MockTransport

from s2gos_client import Client, ClientConfig, __version__
from s2gos_client.cli.cli import cli


def invoke_cli(*args: str) -> typer.testing.Result:
    def get_mock_client(_config_path: str | None):
        return Client(config=ClientConfig(), _transport=MockTransport())

    runner = typer.testing.CliRunner()
    return runner.invoke(cli, args, obj={"get_client": get_mock_client})


class CliTest(TestCase):
    def test_help(self):
        result = invoke_cli("--help")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertIn("tool for the S2GOS service.", result.output)

    def test_version(self):
        result = invoke_cli("--version")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(__version__ + "\n", result.output)

    def test_configure(self):
        config_path = Path("config.cfg")
        result = invoke_cli(
            "configure",
            "-c",
            str(config_path),
            "-u",
            "bibo",
            "-t",
            "1234",
            "-s",
            "http://localhorst:2357",
        )
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertTrue(config_path.exists())
        config_path.unlink()

    def test_get_processes(self):
        result = invoke_cli("list-processes")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual("links: []\nprocesses: []\n\n", result.output)

    def test_get_process(self):
        result = invoke_cli("get-process", "sleep_a_while")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual("id: ID-1\nversion: ''\n\n", result.output)

    def test_create_request(self):
        result = invoke_cli("create-request", "sleep_a_while")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            "inputs: {}\nprocess_id: ID-1\n\n",
            result.output,
        )

    def test_validate_request(self):
        result = invoke_cli(
            "validate-request", "sleep_a_while", "-i", "duration=120", "-i", "fail=true"
        )
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            "inputs:\n  duration: 120\n  fail: true\nprocess_id: sleep_a_while\n\n",
            result.output,
        )

    def test_execute_process(self):
        result = invoke_cli(
            "execute-process", "sleep_a_while", "-i", "duration=120", "-i", "fail=true"
        )
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            "jobID: ''\nstatus: accepted\ntype: process\n\n", result.output
        )

    def test_list_jobs(self):
        result = invoke_cli("list-jobs")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual("jobs: []\nlinks: []\n\n", result.output)

    def test_get_job(self):
        result = invoke_cli("get-job", "job_4")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            "jobID: ''\nstatus: accepted\ntype: process\n\n", result.output
        )

    def test_dismiss_job(self):
        result = invoke_cli("dismiss-job", "job_4")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            "jobID: ''\nstatus: accepted\ntype: process\n\n", result.output
        )

    def test_get_job_results(self):
        result = invoke_cli("get-job-results", "job_4")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual("null\n...\n\n", result.output)

    @classmethod
    def get_result_msg(cls, result: typer.testing.Result):
        if result.exit_code != 0:
            return (
                f"stdout was: [{result.stdout}]\n"
                f"stderr was: [{result.stderr}]\n"
                f"exception was: {result.exception}"
            )
        else:
            return None


class CliWithRealClientTest(TestCase):
    def test_get_processes(self):
        """Test code in app so that the non-mocked Client is used."""
        runner = typer.testing.CliRunner()
        result = runner.invoke(cli, ["list-processes"])
        # May succeed if dev server is running
        self.assertTrue(
            result.exit_code in (0, 1, 3), msg=f"exit code was {result.exit_code}"
        )
        if result.exit_code != 0:
            print(result.output)
