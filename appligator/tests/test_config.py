#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import textwrap
from pathlib import Path

import pytest

from appligator.config import AppligatorConfig, load_config


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "appligator-config.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


class TestLoadConfig:
    def test_empty_file_returns_defaults(self, tmp_path):
        p = _write(tmp_path, "")
        cfg = load_config(p)
        assert cfg == AppligatorConfig()

    def test_image_name(self, tmp_path):
        p = _write(tmp_path, "image_name: myrepo/myimage:1.0")
        assert load_config(p).image_name == "myrepo/myimage:1.0"

    def test_dag_name(self, tmp_path):
        p = _write(tmp_path, "dag_name: my_dag")
        assert load_config(p).dag_name == "my_dag"

    def test_secret_names(self, tmp_path):
        p = _write(tmp_path, """\
            secret_names:
              - secret-a
              - secret-b
        """)
        assert load_config(p).secret_names == ["secret-a", "secret-b"]

    def test_resource_fields(self, tmp_path):
        p = _write(tmp_path, """\
            cpu_request: 500m
            memory_request: 1Gi
            cpu_limit: "2"
            memory_limit: 4Gi
        """)
        cfg = load_config(p)
        assert cfg.cpu_request == "500m"
        assert cfg.memory_request == "1Gi"
        assert cfg.cpu_limit == "2"
        assert cfg.memory_limit == "4Gi"

    def test_pvc_mounts(self, tmp_path):
        p = _write(tmp_path, """\
            pvc_mounts:
              - name: my-vol
                claim_name: my-pvc
                mount_path: /mnt/data
        """)
        cfg = load_config(p)
        assert len(cfg.pvc_mounts) == 1
        pvc = cfg.pvc_mounts[0]
        assert pvc.name == "my-vol"
        assert pvc.claim_name == "my-pvc"
        assert pvc.mount_path == "/mnt/data"

    def test_config_map_mount_without_sub_path(self, tmp_path):
        p = _write(tmp_path, """\
            config_map_mounts:
              - name: my-cm
                config_map_name: app-config
                mount_path: /etc/config
        """)
        cfg = load_config(p)
        cm = cfg.config_map_mounts[0]
        assert cm.name == "my-cm"
        assert cm.config_map_name == "app-config"
        assert cm.mount_path == "/etc/config"
        assert cm.sub_path is None

    def test_config_map_mount_with_sub_path(self, tmp_path):
        p = _write(tmp_path, """\
            config_map_mounts:
              - name: settings
                config_map_name: app-config
                mount_path: /app/settings.yaml
                sub_path: settings.yaml
        """)
        cm = load_config(p).config_map_mounts[0]
        assert cm.sub_path == "settings.yaml"

    def test_full_config(self, tmp_path):
        p = _write(tmp_path, """\
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
        """)
        cfg = load_config(p)
        assert cfg.image_name == "myrepo/myimage:latest"
        assert cfg.dag_name == "my_workflow"
        assert cfg.secret_names == ["s2gos-credentials"]
        assert cfg.pvc_mounts[0].claim_name == "s2gos-output-pvc"
        assert cfg.config_map_mounts[0].sub_path == "s2gos_settings.yaml"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_unknown_field_raises(self, tmp_path):
        p = _write(tmp_path, "not_a_real_field: oops")
        with pytest.raises(Exception):
            load_config(p)
