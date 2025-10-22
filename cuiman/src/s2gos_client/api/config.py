#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel

from .defaults import DEFAULT_CONFIG_PATH, DEFAULT_SERVER_URL


class ClientConfig(BaseModel):
    """Client configuration.

    Args:
        user_name: name of the registered S2GOS user
        access_token: API access token
        server_url: server API URL
    """

    user_name: Optional[str] = None
    access_token: Optional[str] = None
    server_url: Optional[str] = None

    def _repr_json_(self):
        return self.model_dump(mode="json", by_alias=True), dict(
            root="Client configuration:"
        )

    @classmethod
    def create(
        cls,
        *,
        config: Optional["ClientConfig"] = None,
        config_path: Optional[Path | str] = None,
        server_url: Optional[str] = None,
        user_name: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> "ClientConfig":
        config_dict = {"server_url": DEFAULT_SERVER_URL}

        # 1. from file
        file_config = cls.from_file(config_path=config_path)
        if file_config is not None:
            config_dict.update(file_config.to_dict())

        # 2. from env
        env_config = cls.from_env()
        if env_config is not None:
            config_dict.update(env_config.to_dict())

        # 3. from config
        if config is not None:
            config_dict.update(config.to_dict())

        # 4. from args
        args_config = ClientConfig(
            user_name=user_name,
            access_token=access_token,
            server_url=server_url,
        )
        config_dict.update(args_config.to_dict())

        return ClientConfig(**config_dict)

    @classmethod
    def from_file(
        cls, config_path: Optional[str | Path] = None
    ) -> Optional["ClientConfig"]:
        config_path_: Path = cls.normalize_config_path(config_path)
        if not config_path_.exists():
            return None
        with config_path_.open("rt") as stream:
            # Note, we may switch TOML
            config_dict = yaml.safe_load(stream)
        return ClientConfig(**config_dict)

    @classmethod
    def from_env(cls) -> Optional["ClientConfig"]:
        config_dict: dict[str, Any] = {}
        for field_name, _field_info in ClientConfig.model_fields.items():
            env_var_name = "S2GOS_" + field_name.upper()
            if env_var_name in os.environ:
                config_dict[field_name] = os.environ[env_var_name]
        return ClientConfig(**config_dict) if config_dict else None

    def write(self, config_path: Optional[str | Path] = None) -> Path:
        config_path = self.normalize_config_path(config_path)
        config_path.parent.mkdir(exist_ok=True)
        with config_path.open("wt") as stream:
            yaml.dump(
                self.model_dump(mode="json", by_alias=True, exclude_none=True), stream
            )
        return config_path

    @classmethod
    def normalize_config_path(cls, config_path) -> Path:
        return (
            config_path
            if isinstance(config_path, Path)
            else (Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
        )

    def to_dict(self):
        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_defaults=True,
            exclude_unset=True,
        )
