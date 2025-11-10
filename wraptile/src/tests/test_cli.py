#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from gavicore.util.testing import set_env_cm
from wraptile import __version__
from wraptile.cli import cli, parse_cli_service_options, new_cli
from wraptile.constants import ENV_VAR_SERVICE

runner = CliRunner()


class CliTest(TestCase):
    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        self.assertEqual(0, result.exit_code)
        self.assertIn(
            "`wraptile` is a web server made for wrapping workflow",
            result.output,
        )

    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        self.assertEqual(0, result.exit_code)
        self.assertEqual(__version__ + "\n", result.output)

    def test_parse_cli_service_options(self):
        # noinspection PyTypeChecker
        ctx = typer.Context(
            cli,
            allow_extra_args=False,
            allow_interspersed_args=False,
            ignore_unknown_options=False,
        )
        env_var_value = "my.service:service --workers=5 --threads"
        with set_env_cm(**{ENV_VAR_SERVICE: env_var_value}):
            self.assertEqual([], parse_cli_service_options(ctx, None))
            self.assertEqual([], parse_cli_service_options(ctx, []))
            self.assertEqual(
                ["another:service", "--name=bibo"],
                parse_cli_service_options(ctx, ["another:service", "--name=bibo"]),
            )
            self.assertEqual(
                ["my.service:service", "--workers=5", "--threads"],
                parse_cli_service_options(ctx, [env_var_value]),
            )

    @patch("uvicorn.run")
    def test_run(self, mock: MagicMock):
        result = runner.invoke(
            cli,
            [
                "run",
                "--",
                "wraptile.services.local.testing:service",
                "--processes",
                "--max-workers=4",
            ],
        )
        self.assertEqual(0, result.exit_code)
        mock.assert_called_with(
            "wraptile.main:app", host="127.0.0.1", port=8008, reload=False
        )

    @patch("uvicorn.run")
    def test_dev(self, mock: MagicMock):
        result = runner.invoke(
            cli,
            [
                "dev",
                "--",
                "wraptile.services.local.testing:service",
                "--no-processes",
                "--max-workers=4",
            ],
        )
        self.assertEqual(0, result.exit_code)
        mock.assert_called_with(
            "wraptile.main:app", host="127.0.0.1", port=8008, reload=True
        )


class CustomizedCliTest(TestCase):
    def test_version(self):
        customized_cli = new_cli("foobar", version="1.0.3")
        result = runner.invoke(customized_cli, ["--version"])
        self.assertEqual(0, result.exit_code)
        self.assertEqual(f"1.0.3 (wraptile {__version__})\n", result.output)
