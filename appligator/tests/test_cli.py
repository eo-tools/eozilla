#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

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
            "Generate various application formats from your processes.",
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
        with patch(
            "appligator.airflow.gen_image.gen_image",
            return_value="fake-image:latest",
        ):
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
                self.assertTrue(len(list(files)) >= 5)

    def test_pvc_mount_appears_in_generated_dag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--pvc-mount",
                    "my-vol:my-pvc:/mnt/data",
                ],
            )
            self.assertEqual(0, result.exit_code, msg=result.output)
            dag_files = list(Path(tmpdir).glob("*.py"))
            self.assertTrue(len(dag_files) >= 1)
            content = dag_files[0].read_text(encoding="utf-8")
            self.assertIn("persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name='my-pvc')", content)
            self.assertIn("k8s.V1VolumeMount(name='my-vol', mount_path='/mnt/data')", content)

    def test_config_map_mount_appears_in_generated_dag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--config-map-mount",
                    "my-cm:app-config:/etc/config",
                ],
            )
            self.assertEqual(0, result.exit_code, msg=result.output)
            dag_files = list(Path(tmpdir).glob("*.py"))
            content = dag_files[0].read_text(encoding="utf-8")
            self.assertIn("config_map=k8s.V1ConfigMapVolumeSource(name='app-config')", content)
            self.assertIn("k8s.V1VolumeMount(name='my-cm', mount_path='/etc/config')", content)
            self.assertNotIn("sub_path", content)

    def test_config_map_mount_with_sub_path_appears_in_generated_dag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--config-map-mount",
                    "settings:app-config:/app/settings.yaml:settings.yaml",
                ],
            )
            self.assertEqual(0, result.exit_code, msg=result.output)
            dag_files = list(Path(tmpdir).glob("*.py"))
            content = dag_files[0].read_text(encoding="utf-8")
            self.assertIn("sub_path='settings.yaml'", content)

    def test_invalid_pvc_mount_format_exits_with_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--pvc-mount",
                    "only-two-parts:missing-mount-path",
                ],
            )
            self.assertEqual(1, result.exit_code)
            self.assertIn("--pvc-mount must be name:claim_name:mount_path", result.output)

    def test_invalid_config_map_mount_format_exits_with_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--config-map-mount",
                    "only-one-part",
                ],
            )
            self.assertEqual(1, result.exit_code)
            self.assertIn("--config-map-mount must be", result.output)
