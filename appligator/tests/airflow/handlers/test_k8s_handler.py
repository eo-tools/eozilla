#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import unittest

from appligator.airflow.handlers.k8s_handler import KubernetesOperatorHandler
from appligator.airflow.models import ConfigMapMount, PvcMount, TaskIR


class TestKubernetesOperatorHandler(unittest.TestCase):
    def setUp(self):
        self.handler = KubernetesOperatorHandler()

    def test_supports_kubernetes(self):
        task = TaskIR(id="t", runtime="kubernetes", inputs={})
        self.assertTrue(self.handler.supports(task))

    def test_does_not_support_other_runtimes(self):
        task = TaskIR(id="t", runtime="syn-python", inputs={})
        self.assertFalse(self.handler.supports(task))

    def test_full_render_output(self):
        task = TaskIR(
            id="main",
            runtime="kubernetes",
            func_module="my.module",
            func_qualname="my_func",
            image="my-image",
            inputs={"x": "param:x", "y": "xcom:second_step:y"},
            outputs=["out"],
            depends_on=[],
        )

        rendered = self.handler.render(task)

        expected = """
    tasks["main"] = KubernetesPodOperator(
        task_id="main",
        image="my-image",
        cmds=["python", "/app/run_step.py"],
        arguments=[json.dumps({
            "func_module": "my.module",
            "func_qualname": "my_func",
            "inputs": {"x": "{{ params.x }}",
"y": "{{ ti.xcom_pull(task_ids=\'second_step\')[\'y\'] }}"},
            "output_keys": [\'out\'],
        })],
        do_xcom_push=True,
    )
"""
        self.assertEqual(
            expected,
            rendered,
        )

    def test_render_with_pvc_mount(self):
        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
            pvc_mounts=[
                PvcMount(name="vol", claim_name="my-pvc", mount_path="/mnt/vol")
            ],
        )
        rendered = self.handler.render(task)
        self.assertIn(
            "volumes=[k8s.V1Volume(name='vol', "
            "persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name='my-pvc'))]",
            rendered,
        )
        self.assertIn(
            "volume_mounts=[k8s.V1VolumeMount(name='vol', mount_path='/mnt/vol')]",
            rendered,
        )

    def test_render_with_config_map_mount_no_sub_path(self):
        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
            config_map_mounts=[
                ConfigMapMount(name="cm", config_map_name="my-cm", mount_path="/etc/cm")
            ],
        )
        rendered = self.handler.render(task)
        self.assertIn(
            "volumes=[k8s.V1Volume(name='cm', config_map=k8s.V1ConfigMapVolumeSource(name='my-cm'))]",
            rendered,
        )
        self.assertIn(
            "volume_mounts=[k8s.V1VolumeMount(name='cm', mount_path='/etc/cm')]",
            rendered,
        )
        self.assertNotIn("sub_path", rendered)

    def test_render_with_config_map_mount_with_sub_path(self):
        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
            config_map_mounts=[
                ConfigMapMount(
                    name="cm",
                    config_map_name="my-cm",
                    mount_path="/app/settings.yaml",
                    sub_path="settings.yaml",
                )
            ],
        )
        rendered = self.handler.render(task)
        self.assertIn(
            "k8s.V1VolumeMount(name='cm', mount_path='/app/settings.yaml', sub_path='settings.yaml')",
            rendered,
        )

    def test_render_with_pvc_and_config_map_mounts(self):
        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
            pvc_mounts=[
                PvcMount(name="data", claim_name="data-pvc", mount_path="/mnt/data")
            ],
            config_map_mounts=[
                ConfigMapMount(
                    name="cfg", config_map_name="app-cfg", mount_path="/etc/cfg"
                )
            ],
        )
        rendered = self.handler.render(task)
        self.assertIn(
            "k8s.V1PersistentVolumeClaimVolumeSource(claim_name='data-pvc')", rendered
        )
        self.assertIn("k8s.V1ConfigMapVolumeSource(name='app-cfg')", rendered)
        self.assertIn(
            "k8s.V1VolumeMount(name='data', mount_path='/mnt/data')", rendered
        )
        self.assertIn("k8s.V1VolumeMount(name='cfg', mount_path='/etc/cfg')", rendered)

    def test_render_with_env_from_secrets(self):
        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
            env_from_secrets=["my-secret", "other-secret"],
        )
        rendered = self.handler.render(task)
        self.assertIn(
            "env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name='my-secret')), "
            "k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name='other-secret'))]",
            rendered,
        )

    def test_no_env_from_block_when_no_secrets(self):
        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
        )
        self.assertNotIn("env_from=", self.handler.render(task))

    def test_render_with_resources(self):
        from appligator.airflow.models import ResourceRequirements

        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
            resources=ResourceRequirements(
                cpu_request="500m",
                memory_request="1Gi",
                cpu_limit="1",
                memory_limit="2Gi",
            ),
        )
        rendered = self.handler.render(task)
        self.assertIn("container_resources=k8s.V1ResourceRequirements(", rendered)
        self.assertIn("requests=", rendered)
        self.assertIn("limits=", rendered)
        self.assertIn("'cpu': '500m'", rendered)
        self.assertIn("'memory': '1Gi'", rendered)

    def test_render_with_partial_resources(self):
        from appligator.airflow.models import ResourceRequirements

        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
            resources=ResourceRequirements(cpu_request="500m"),
        )
        rendered = self.handler.render(task)
        self.assertIn("requests=", rendered)
        self.assertNotIn("limits=", rendered)

    def test_no_volume_blocks_when_no_mounts(self):
        task = TaskIR(
            id="t",
            runtime="kubernetes",
            func_module="m",
            func_qualname="f",
            image="img",
            inputs={},
            outputs=[],
        )
        rendered = self.handler.render(task)
        self.assertNotIn("volumes=", rendered)
        self.assertNotIn("volume_mounts=", rendered)
