#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import tempfile
from pathlib import Path
from unittest import TestCase

from typer.testing import CliRunner

from appligator import __version__
from appligator.cli import cli

runner = CliRunner()


class CliTest(TestCase):
    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        print(result.output)
        self.assertEqual(0, result.exit_code)
        self.assertIn(
            "Generate various application formats from your processing workflows.",
            result.output,
        )

    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        self.assertEqual(0, result.exit_code)
        self.assertEqual(__version__ + "\n", result.output)

    def test_missing_process_registry_spec(self):
        result = runner.invoke(cli, [])
        self.assertEqual(1, result.exit_code)

    def test_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                ],
            )
            self.assertEqual(0, result.exit_code, msg=result.output)
            files = Path(tmpdir).glob("*.py")
            self.assertTrue(len(list(files)) >= 4)
