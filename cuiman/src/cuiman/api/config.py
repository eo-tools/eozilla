#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from functools import cache
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Optional,
    TypeAlias,
)

import yaml
from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from gavicore.models import InputDescription, ProcessDescription, ProcessSummary

from .auth import AuthConfig
from .defaults import DEFAULT_API_URL
from .opener import JobResultOpener, JobResultOpenerRegistry


class ClientConfig(AuthConfig, BaseSettings):
    """Client configuration.

    Args:
        api_url: a URL pointing to a service compliant with
            the OCG API - Processes.
    """

    model_config = SettingsConfigDict(
        env_prefix="EOZILLA_",
        extra="forbid",
    )

    default_config: ClassVar["ClientConfig"]
    """
    Default instance. 
    Used to create pre-configured instances of this class.
    Designed to be overridden by library clients.
    """

    default_path: ClassVar[Path]
    """
    Name of the configuration's local default path. 
    Used for configuration persistence in `~/.<config_name>/`.
    Designed to be overridden by library clients.
    """

    return_type_map: ClassVar[dict[type, type]] = {}
    """
    A mapping from a hard-coded client return type to a 
    custom return type. The hard-coded return type is usually a 
    model class from `gavicore.models`. The custom return type 
    typically extends the model class.  
    Designed to be configured by library clients.
    The default mapping is empty.
    """

    api_url: Annotated[Optional[str], Field(title="Process API URL")] = None
    """
    The URL of the server that provides a web API compliant with
    OGC API - Processes, Part 1 - Core.
    """

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
        load_file: bool = True,
        **config_kwargs,
    ) -> "ClientConfig":
        # 0. from defaults
        config_dict = cls.default_config.to_dict()

        # 1. from file
        if load_file:
            file_config = cls.from_file(config_path=config_path)
            if file_config is not None:
                _update_if_not_none(config_dict, file_config.to_dict())

        # 2. from env
        env_config = cls()
        _update_if_not_none(config_dict, env_config.to_dict())

        # 3. from config
        if config is not None:
            _update_if_not_none(config_dict, config.to_dict())

        # 4. from kwargs
        _update_if_not_none(config_dict, config_kwargs)

        return cls.new_instance(**config_dict)

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
        return cls.new_instance(**config_dict)

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
            else (Path(config_path) if config_path else cls.default_path)
        )

    @classmethod
    def new_instance(
        cls,
        **kwargs: Any,
    ) -> "ClientConfig":
        config_cls = type(ClientConfig.default_config)
        assert issubclass(config_cls, ClientConfig)
        return config_cls(**kwargs)

    def to_dict(self):
        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_defaults=True,
            exclude_unset=True,
        )

    # noinspection PyMethodParameters
    @field_validator("api_url")
    def validate_api_url(cls, v: str | None) -> str | None:
        return None if v is None or v == "" else str(HttpUrl(v))

    @classmethod
    def register_job_result_opener(
        cls, opener_type: type[JobResultOpener]
    ) -> Callable[[], None]:
        """Register a job result opener.

        Args:
            opener_type: The type of the opener to be registered.

        Returns:
            A function that can be called to unregister the opener.
        """
        return cls.get_job_result_opener_registry().register(opener_type)

    @classmethod
    @cache
    def get_job_result_opener_registry(cls) -> JobResultOpenerRegistry:
        """
        Get the registry for openers that are used to open job results.

        Use it to register custom openers for special job results.

        Note that the registry contains types/classes, not instances.
        """
        return JobResultOpenerRegistry.create_default()


# Set Eozilla defaults.
# Cuiman applications might want to change them.
ClientConfig.default_config = ClientConfig(api_url=DEFAULT_API_URL)
ClientConfig.default_path = Path("~").expanduser() / ".eozilla" / "config"

ProcessPredicate: TypeAlias = Callable[[ProcessSummary], bool]
"""
Type that describes the [accept_process][ClientConfig.accept_process] class method.
"""

InputPredicate: TypeAlias = Callable[[ProcessDescription, str, InputDescription], bool]
"""
Type that describes the [accept_input][ClientConfig.accept_process] class method.
"""

AdvancedInputPredicate: TypeAlias = Callable[
    [ProcessDescription, str, InputDescription], bool
]


def _update_if_not_none(target: dict[str, Any], updates: dict[str, Any]):
    target.update({k: v for k, v in updates.items() if v is not None})
