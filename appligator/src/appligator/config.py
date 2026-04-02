#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from appligator.airflow.models import ConfigMapMount, PvcMount


class AppligatorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """
    Configuration for the appligator CLI, loadable from a YAML file.

    All fields are optional. CLI flags take precedence over values set here;
    this file provides defaults that would otherwise require many flags to be
    repeated on every invocation.

    Example appligator-config.yaml:

        image_name: myrepo/myimage:latest
        dag_name: my_workflow
        secret_names:
          - s2gos-credentials
        cpu_request: 500m
        memory_request: 1Gi
        cpu_limit: "1"
        memory_limit: 2Gi
        pvc_mounts:
          - name: s2gos-output
            claim_name: s2gos-output-pvc
            mount_path: /mnt/s2gos-output
        config_map_mounts:
          - name: s2gos-settings
            config_map_name: s2gos-settings
            mount_path: /opt/pixi/s2gos_settings.yaml
            sub_path: s2gos_settings.yaml
    """

    image_name: str | None = None
    dag_name: str | None = None
    secret_names: list[str] = Field(default_factory=list)
    cpu_request: str | None = None
    memory_request: str | None = None
    cpu_limit: str | None = None
    memory_limit: str | None = None
    pvc_mounts: list[PvcMount] = Field(default_factory=list)
    config_map_mounts: list[ConfigMapMount] = Field(default_factory=list)


def load_config(path: Path) -> AppligatorConfig:
    """Load an AppligatorConfig from a YAML file.

    Args:
        path: Path to the YAML config file.

    Returns:
        A validated AppligatorConfig instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file contains invalid YAML or unknown fields.
    """
    import yaml

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AppligatorConfig.model_validate(data or {})
