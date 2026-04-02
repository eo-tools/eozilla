#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from appligator.airflow.handlers.base_handler import OperatorHandler
from appligator.airflow.models import TaskIR


class KubernetesOperatorHandler(OperatorHandler):
    """
    OperatorHandler implementation for tasks executed inside Kubernetes pods.

    This handler renders TaskIR objects with runtime="kubernetes" into
    KubernetesPodOperator definitions. Task execution is delegated to
    `run_step.main`, which resolves and invokes the target function inside
    the container.
    """

    def supports(self, task: TaskIR) -> bool:
        return task.runtime == "kubernetes"

    def render(self, task: TaskIR) -> str:
        from appligator.airflow.renderer import render_task_inputs

        inputs = render_task_inputs(task.inputs)

        env_from_block = ""
        if task.env_from_secrets:
            entries = ", ".join(
                f"k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name={name!r}))"
                for name in task.env_from_secrets
            )
            env_from_block = f"\n        env_from=[{entries}],"

        resources_block = ""
        if task.resources:
            r = task.resources
            requests = {k: v for k, v in {"cpu": r.cpu_request, "memory": r.memory_request}.items() if v}
            limits = {k: v for k, v in {"cpu": r.cpu_limit, "memory": r.memory_limit}.items() if v}
            requests_str = f"requests={requests!r}, " if requests else ""
            limits_str = f"limits={limits!r}" if limits else ""
            resources_block = f"\n        container_resources=k8s.V1ResourceRequirements({requests_str}{limits_str}),"

        volumes_block = ""
        volume_mounts_block = ""
        if task.pvc_mounts or task.config_map_mounts:
            vol_entries = []
            mount_entries = []
            for pvc in task.pvc_mounts:
                vol_entries.append(
                    f"k8s.V1Volume(name={pvc.name!r}, "
                    f"persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name={pvc.claim_name!r}))"
                )
                mount_entries.append(
                    f"k8s.V1VolumeMount(name={pvc.name!r}, mount_path={pvc.mount_path!r})"
                )
            for cm in task.config_map_mounts:
                vol_entries.append(
                    f"k8s.V1Volume(name={cm.name!r}, "
                    f"config_map=k8s.V1ConfigMapVolumeSource(name={cm.config_map_name!r}))"
                )
                sub = f", sub_path={cm.sub_path!r}" if cm.sub_path else ""
                mount_entries.append(
                    f"k8s.V1VolumeMount(name={cm.name!r}, mount_path={cm.mount_path!r}{sub})"
                )
            volumes_block = f"\n        volumes=[{', '.join(vol_entries)}],"
            volume_mounts_block = f"\n        volume_mounts=[{', '.join(mount_entries)}],"

        return f"""
    tasks["{task.id}"] = KubernetesPodOperator(
        task_id="{task.id}",
        image="{task.image}",
        cmds=["python", "/app/run_step.py"],
        arguments=[json.dumps({{
            "func_module": "{task.func_module}",
            "func_qualname": "{task.func_qualname}",
            "inputs": {{{inputs}}},
            "output_keys": {task.outputs},
        }})],{env_from_block}{resources_block}{volumes_block}{volume_mounts_block}
        do_xcom_push=True,
    )
"""
