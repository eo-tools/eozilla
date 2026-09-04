#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from functools import cache
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Optional,
    TypeAlias,
)

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict

from gavicore.models import InputDescription, ProcessDescription, ProcessSummary

from .auth import AuthConfig, AuthConfigBase, NoAuthConfig
from .auth.secret_store import load_auth_secrets, save_auth_secrets
from .defaults import DEFAULT_API_URL
from .opener import JobResultOpener, JobResultOpenerRegistry


class ClientConfig(BaseSettings):
    """Client configuration.

    Args:
        api_url: a URL pointing to a service compliant with
            the OCG API - Processes.
    """

    model_config = SettingsConfigDict(
        env_prefix="EOZILLA_",
        env_nested_delimiter="__",
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

    auth: AuthConfig = Field(default_factory=NoAuthConfig)
    """Authentication configuration selected by its ``auth_type`` field."""

    @property
    def auth_headers(self) -> dict[str, str]:
        """Return the HTTP authentication headers for this client."""
        return self.auth.auth_headers

    def _maybe_make_token_refresher(
        self,
    ) -> Callable[[], dict[str, str]] | None:
        """Create a synchronous token renewal callback when supported."""
        return self.auth.make_token_refresher()

    def _make_async_token_refresher(
        self,
    ) -> Callable[[], Awaitable[dict[str, str]]] | None:
        """Create an asynchronous token renewal callback when supported."""
        return self.auth.make_async_token_refresher()

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
        **config_kwargs,
    ) -> "ClientConfig":
        # 1. from file
        file_config = cls.from_file(config_path=config_path)
        # 2. from env. Read raw settings so a partial nested auth override can
        # be merged with the auth model loaded from defaults or a file before
        # the discriminated union is validated.
        env_config = EnvSettingsSource(cls)()

        def merge_config_sources(
            auth_secrets: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            config_dict = cls.default_config.to_dict()
            if file_config is not None:
                _update_if_not_none(config_dict, file_config.to_dict())
            if auth_secrets:
                _update_if_not_none(config_dict, {"auth": auth_secrets})
            _update_config_from_env(config_dict, env_config)
            if config is not None:
                _update_if_not_none(config_dict, config.to_dict())
            _update_if_not_none(config_dict, config_kwargs)
            return config_dict

        config_dict = merge_config_sources()
        resolved_config = cls.new_instance(**config_dict)
        if file_config is None or _has_auth_credentials(resolved_config):
            return resolved_config

        auth_secrets = load_auth_secrets(
            cls.normalize_config_path(config_path),
            resolved_config.api_url or "",
            resolved_config.auth.auth_type,
        )
        auth_secrets = {
            name: value
            for name, value in auth_secrets.items()
            if name in resolved_config.auth.secret_fields
        }
        if not auth_secrets:
            return resolved_config
        resolved_config = cls.new_instance(**merge_config_sources(auth_secrets))
        _set_auth_secret_persistor(
            resolved_config,
            cls.normalize_config_path(config_path),
        )
        return resolved_config

    @classmethod
    def from_file(
        cls, config_path: Optional[str | Path] = None
    ) -> Optional["ClientConfig"]:
        config_dict = cls.read_file_data(config_path)
        if config_dict is None:
            return None
        if _is_legacy_file_config(config_dict):
            raise ValueError(
                "Legacy configuration format detected, please run 'cuiman configure'"
            )
        config_cls = type(ClientConfig.default_config)
        assert issubclass(config_cls, ClientConfig)
        # Do not call BaseSettings.__init__: it would merge environment values
        # into this file-only configuration before ClientConfig.create() can
        # perform its intentional merge. BaseModel.__init__ still validates
        # config_dict, but does not load any settings sources.
        instance = object.__new__(config_cls)
        BaseModel.__init__(instance, **config_dict)
        return instance

    def write(self, config_path: Optional[str | Path] = None) -> Path:
        config_path = self.normalize_config_path(config_path)
        config_path.parent.mkdir(exist_ok=True)
        with config_path.open("wt") as stream:
            yaml.dump(self.to_file_dict(), stream)
        return config_path

    @classmethod
    def read_file_data(
        cls, config_path: Optional[str | Path] = None
    ) -> dict[str, Any] | None:
        """Read an unvalidated configuration mapping from a file, if it exists."""
        config_path_ = cls.normalize_config_path(config_path)
        if not config_path_.exists():
            return None
        with config_path_.open("rt") as stream:
            # Note, we may switch TOML.
            config_dict = yaml.safe_load(stream)
        if config_dict is None:
            return None
        if not isinstance(config_dict, dict):
            raise ValueError("Configuration file must contain a mapping.")
        return config_dict

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
        config_dict = self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_defaults=True,
            exclude_unset=True,
        )
        if "auth" in config_dict:
            config_dict["auth"]["auth_type"] = self.auth.auth_type
        return config_dict

    def to_file_dict(self) -> dict[str, Any]:
        """Return a configuration mapping that omits authentication secrets."""
        config_dict = self.model_dump(
            mode="json",
            by_alias=True,
            exclude={"auth"},
            exclude_none=True,
        )
        config_dict["auth"] = self.auth.to_public_dict()
        return config_dict

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
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _update_if_not_none(target[key], value)
        else:
            target[key] = value


def _has_auth_credentials(config: ClientConfig) -> bool:
    """Return whether an authentication config can create request headers."""
    try:
        _ = config.auth_headers
    except ValueError:
        return False
    return True


def _set_auth_secret_persistor(config: ClientConfig, config_path: Path) -> None:
    """Persist updated token values to the keyring associated with a config file."""

    def persist(auth: AuthConfigBase) -> None:
        save_auth_secrets(
            config_path,
            config.api_url or "",
            auth.auth_type,
            auth.to_secret_dict(),
        )

    config.auth.set_secret_persistor(persist)


###############################################################
# -- Config file legacy management
###############################################################


def _update_config_from_env(target: dict[str, Any], env_config: dict[str, Any]) -> None:
    """Merge environment settings, replacing auth when its type is selected.

    An environment ``auth_type`` chooses a new discriminated auth model, so
    retaining fields from an auth model selected by a configuration file would
    make them invalid extra inputs.
    """
    auth_config = env_config.get("auth")
    if isinstance(auth_config, dict) and "auth_type" in auth_config:
        target["auth"] = auth_config
        env_config = {key: value for key, value in env_config.items() if key != "auth"}
    _update_if_not_none(target, env_config)


_SECRET_AUTH_FIELDS = {
    "access_token",
    "api_key",
    "client_secret",
    "password",
    "refresh_token",
    "token",
    "username",
}


def _is_legacy_file_config(config: dict[str, Any]) -> bool:
    """Return whether a configuration uses a former secret-bearing file format."""
    if "auth_type" in config:
        return True
    auth_config = config.get("auth")
    return isinstance(auth_config, dict) and bool(
        _SECRET_AUTH_FIELDS.intersection(auth_config)
    )
