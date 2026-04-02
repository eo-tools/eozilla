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

    def test_dag_name_with_multiple_processes_uses_suffix(self):
        """Exercises the multi + dag_name branch: file_stem = f"{dag_name}_{process_id}"."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                [
                    # registry has multiple processes so multi=True
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--dag-name",
                    "mydag",
                ],
            )
            self.assertEqual(0, result.exit_code, msg=result.output)
            stems = [f.stem for f in Path(tmpdir).glob("*.py")]
            # every file should be prefixed with the dag_name
            self.assertTrue(all(s.startswith("mydag_") for s in stems), stems)

    def test_no_skip_build_calls_gen_image(self):
        """Exercises the --no-skip-build path (gen_image call)."""
        with patch(
            "appligator.airflow.gen_image.gen_image",
            return_value="built-image:latest",
        ) as mock_gen_image:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    [
                        "wraptile.services.local.testing:service.process_registry",
                        "--dags-folder",
                        tmpdir,
                        "--no-skip-build",
                    ],
                )
                self.assertEqual(0, result.exit_code, msg=result.output)
                mock_gen_image.assert_called()

    def test_config_file_values_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "appligator-config.yaml"
            cfg.write_text(
                "secret_names:\n  - from-file-secret\n"
                "pvc_mounts:\n"
                "  - name: file-vol\n"
                "    claim_name: file-pvc\n"
                "    mount_path: /mnt/file\n",
                encoding="utf-8",
            )
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--config-file",
                    str(cfg),
                ],
            )
            self.assertEqual(0, result.exit_code, msg=result.output)
            dag_files = list(Path(tmpdir).glob("*.py"))
            content = dag_files[0].read_text(encoding="utf-8")
            self.assertIn("from-file-secret", content)
            self.assertIn("claim_name='file-pvc'", content)

    def test_config_map_mount_from_config_file(self):
        """Exercises the cfg.config_map_mounts fallback in effective_config_map_mounts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "appligator-config.yaml"
            cfg.write_text(
                "config_map_mounts:\n"
                "  - name: file-cm\n"
                "    config_map_name: file-config\n"
                "    mount_path: /etc/file-config\n",
                encoding="utf-8",
            )
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--config-file",
                    str(cfg),
                ],
            )
            self.assertEqual(0, result.exit_code, msg=result.output)
            content = list(Path(tmpdir).glob("*.py"))[0].read_text(encoding="utf-8")
            self.assertIn("config_map=k8s.V1ConfigMapVolumeSource(name='file-config')", content)

    def test_cli_flag_overrides_config_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "appligator-config.yaml"
            cfg.write_text("secret_names:\n  - file-secret\n", encoding="utf-8")
            result = runner.invoke(
                cli,
                [
                    "wraptile.services.local.testing:service.process_registry",
                    "--dags-folder",
                    tmpdir,
                    "--config-file",
                    str(cfg),
                    "--secret-name",
                    "cli-secret",
                ],
            )
            self.assertEqual(0, result.exit_code, msg=result.output)
            dag_files = list(Path(tmpdir).glob("*.py"))
            content = dag_files[0].read_text(encoding="utf-8")
            self.assertIn("cli-secret", content)
            self.assertNotIn("file-secret", content)
