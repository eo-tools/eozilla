#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import typer.testing
import yaml

from cuiman import Client, __version__
from cuiman.cli.cli import cli, new_cli

from ..helpers import MockTransport


def invoke_cli(*args: str) -> typer.testing.Result:
    def get_mock_client(_config_path: str | None):
        return Client(api_url="https://abc.de", _transport=MockTransport())

    runner = typer.testing.CliRunner()
    return runner.invoke(cli, args, obj={"get_client": get_mock_client})


class CliTest(TestCase):
    def test_help(self):
        result = invoke_cli("--help")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertIn("tool.", result.output)

    def test_version(self):
        result = invoke_cli("--version")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(__version__ + "\n", result.output)

    @patch("cuiman.cli.config.login", return_value="dummy-token")
    def test_configure(self, mock_login):
        config_path = Path("config.cfg")
        result = invoke_cli(
            "configure",
            "-c",
            str(config_path),
            "--api-url",
            "http://localhorst:2357",
            "--auth-type",
            "login",
            "--auth-url",
            "http://localhorst:2357/auth/login",
            "--username",
            "bibo",
            "--password",
            "1234",
            "--use-bearer",
        )
        mock_login.assert_called_once()
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertTrue(config_path.exists())
        with open(config_path) as f:
            config = yaml.safe_load(f.read())
            self.assertEqual(
                {
                    "api_url": "http://localhorst:2357/",
                    "auth_type": "login",
                    "auth_url": "http://localhorst:2357/auth/login",
                    "username": "bibo",
                    "password": "1234",
                    "token": "dummy-token",
                    "use_bearer": True,
                    "token_header": "X-Auth-Token",
                    "api_key_header": "X-API-Key",
                },
                config,
            )
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


class CustomizedCliTest(TestCase):
    def test_version(self):
        runner = typer.testing.CliRunner()
        customized_cli = new_cli("foobar", version="1.0.3")
        result = runner.invoke(customized_cli, ["--version"])
        self.assertEqual(0, result.exit_code)
        self.assertEqual(f"1.0.3 (cuiman {__version__})\n", result.output)
