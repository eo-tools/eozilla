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
from pydantic import BaseModel, Field, HttpUrl, PrivateAttr, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    SettingsConfigDict,
)

from gavicore.models import InputDescription, ProcessDescription, ProcessSummary

from .auth import AuthConfig, AuthConfigBase, NoAuthConfig
from .auth.config import has_credentials
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
        hide_input_in_errors=True,
    )

    default_path: ClassVar[Path] = Path("~").expanduser() / ".eozilla" / "config"
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

    api_url: Annotated[Optional[str], Field(title="Process API URL")] = DEFAULT_API_URL
    """
    The URL of the server that provides a web API compliant with
    OGC API - Processes, Part 1 - Core. This is a base URL: Python and app
    requests append endpoint paths with a slash separator. The landing page
    uses the base path followed by a trailing slash.
    """

    auth: AuthConfig = Field(default_factory=NoAuthConfig)
    """Authentication configuration selected by its ``auth_type`` field.

    When resolving settings with ``create()``, an auth model or a dictionary
    containing ``auth_type`` replaces previous auth settings. A dictionary
    without ``auth_type`` merges into the selected configuration. Matching
    keyring credentials may fill missing secrets after resolution.
    """

    _source_path: Path | None = PrivateAttr(default=None)
    _is_resolved: bool = PrivateAttr(default=False)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Give each application an independent return-type extension mapping.

        A mutable class attribute would otherwise be shared by an application
        subclass and Cuiman's base configuration.  Copying at class creation
        preserves registrations inherited up to that point while ensuring later
        registrations cannot leak into unrelated client namespaces.
        """
        super().__init_subclass__(**kwargs)
        if "return_type_map" not in cls.__dict__:
            cls.return_type_map = dict(cls.return_type_map)

    def _repr_json_(self):
        return self.to_file_dict(), dict(root="Client configuration:")

    @classmethod
    def create(
        cls,
        *,
        config: Optional["ClientConfig"] = None,
        config_type: type["ClientConfig"] | None = None,
        config_path: Optional[Path | str] = None,
        resolve_secrets: bool = True,
        **config_kwargs,
    ) -> "ClientConfig":
        """Resolve client settings, optionally skipping stored keyring secrets.

        Keyword settings override ``config``. An ``auth`` model or a dictionary
        containing ``auth_type`` replaces previous authentication settings,
        even when the type is unchanged. A dictionary without ``auth_type``
        merges into the selected authentication configuration, including nested
        mappings; ``None`` values in partial overrides are ignored.

        If a public configuration file exists and the resolved authentication
        lacks usable credentials, matching keyring secrets fill missing values.
        Explicitly supplied credentials take precedence, including after an
        auth replacement. Resolution does not rewrite the configuration file.

        Set ``resolve_secrets=False`` to resolve the effective service and auth
        configuration without requiring readable keyring credentials.
        """
        # 0. Select the application namespace before reading any source.  The
        #    selected Pydantic class owns defaults, schema, dotenv behaviour,
        #    environment prefix, persistence path, and extensions.
        config_cls = cls._select_config_type(config_type, config)

        if (
            config is not None
            and config._is_resolved
            and config_path is None
            and not _has_config_values(config_kwargs)
        ):
            # Wrapping an already resolved configuration is common in the CLI
            # and app.  Re-running sources here could apply a different dotenv
            # value or lose a credential persistor, so retain its exact result.
            return _copy_resolved_config(config)

        if config_path is None and config is not None:
            config_path = config._source_path

        source_path = config_cls.normalize_config_path(config_path)

        # 1. Load the public, file-backed configuration without resolving
        #    environment variables or operating-system credentials yet.
        file_config = config_cls.from_file(config_path=source_path)

        # 2. Read raw dotenv and environment settings.  They must remain raw so
        #    a partial nested auth override can be merged before the
        #    discriminated union is validated.  Process environment deliberately
        #    wins over dotenv, matching Pydantic's normal settings precedence.
        dotenv_config = _model_setting_values(
            config_cls, DotEnvSettingsSource(config_cls)()
        )
        env_config = EnvSettingsSource(config_cls)()

        # 3. Resolve sources from lowest to highest precedence.  Build class
        #    defaults via BaseModel rather than BaseSettings so this first layer
        #    never reads environment variables before the merge is complete.
        config_dict = config_cls._default_values()
        if file_config is not None:
            _update_config(config_dict, file_config.to_dict())
        _update_config(config_dict, dotenv_config)
        _update_config(config_dict, env_config)
        if config is not None:
            _update_config(config_dict, config.to_dict())
        _update_config(config_dict, config_kwargs)

        # 4. Build the effective configuration from all non-keyring sources
        #    without re-resolving Pydantic Settings sources.
        resolved_config = config_cls.new_instance(**config_dict)
        resolved_config._source_path = source_path
        resolved_config._is_resolved = True
        if (
            config is not None
            and resolved_config._source_path
            == config_cls.normalize_config_path(config._source_path)
            and resolved_config.api_url == config.api_url
            and resolved_config.auth.model_dump() == config.auth.model_dump()
        ):
            # Preserve the credential source when wrapping a resolved config,
            # as CLI and generated service clients do. Never carry the hook
            # across an endpoint or authentication override.
            resolved_config.auth = config.auth.model_copy()
        if (
            not resolve_secrets
            or file_config is None
            or has_credentials(resolved_config.auth)
        ):
            return resolved_config

        # 5. A public file configuration without usable credentials may have
        #     matching secrets in the operating-system keyring.
        auth_secrets = load_auth_secrets(
            source_path,
            resolved_config.api_url or "",
            resolved_config.auth.auth_type,
        )
        auth_secrets = {
            name: value
            for name, value in auth_secrets.items()
            if name in resolved_config.auth.secret_fields
        }
        if not auth_secrets:
            _set_auth_secret_persistor(resolved_config, source_path)
            return resolved_config

        # 6. Fill missing credentials in the selected auth configuration.
        #    Explicit values take precedence. Do not replay source overrides:
        #    a complete auth selection would discard the loaded credentials.
        config_dict = resolved_config.to_dict()
        config_dict["auth"] = {
            **auth_secrets,
            **resolved_config.auth.model_dump(mode="json", exclude_none=True),
        }
        resolved_config = config_cls.new_instance(**config_dict)
        resolved_config._is_resolved = True
        _set_auth_secret_persistor(
            resolved_config,
            source_path,
        )
        return resolved_config

    @classmethod
    def from_file(
        cls,
        config_path: Optional[str | Path] = None,
        *,
        config_type: type["ClientConfig"] | None = None,
    ) -> Optional["ClientConfig"]:
        """Load a file using the application's configured schema.

        Missing or empty files return ``None``. Parsing or validation errors
        raise ``ValueError`` with instructions to run ``configure``, without
        exposing file contents. Files that validate are accepted regardless
        of their age or field names. Loading does not rewrite the file, and
        filesystem access errors propagate unchanged.
        """
        try:
            config_cls = cls._select_config_type(config_type)
            config_dict = config_cls.read_file_data(config_path)
            if config_dict is None:
                return None
            # Validate only the file; create() resolves the other settings sources.
            config = cls._new_model_instance(config_cls, **config_dict)
        except (ValueError, TypeError, yaml.YAMLError):
            raise ValueError(
                "Deprecated or illegal configuration file, please run the 'configure' command."
            ) from None
        config._source_path = config_cls.normalize_config_path(config_path)
        return config

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
    def normalize_config_path(
        cls,
        config_path: Path | str | None,
        *,
        config_type: type["ClientConfig"] | None = None,
    ) -> Path:
        """Return a path, using the selected application's default when absent."""
        config_cls = cls._select_config_type(config_type)
        return (
            config_path
            if isinstance(config_path, Path)
            else (Path(config_path) if config_path else config_cls.default_path)
        )

    @classmethod
    def new_instance(
        cls,
        *,
        config_type: type["ClientConfig"] | None = None,
        **kwargs: Any,
    ) -> "ClientConfig":
        # This is the final configuration construction step. Do not invoke
        # BaseSettings.__init__ here: nested environment settings would be
        # merged again and could conflict with the authentication type already
        # selected by the explicit configuration-resolution steps above.
        return cls._new_model_instance(cls._select_config_type(config_type), **kwargs)

    @staticmethod
    def _new_model_instance(
        config_cls: type["ClientConfig"], **kwargs: Any
    ) -> "ClientConfig":
        """Validate explicit values without loading any Settings sources."""
        instance = object.__new__(config_cls)
        BaseModel.__init__(instance, **kwargs)
        return instance

    @classmethod
    def _default_values(cls) -> dict[str, Any]:
        """Return Pydantic field defaults without consulting settings sources."""
        field_defaults = cls._new_model_instance(cls)
        return field_defaults.model_dump(mode="json", by_alias=True, exclude_none=True)

    @classmethod
    def _select_config_type(
        cls,
        config_type: type["ClientConfig"] | None = None,
        config: "ClientConfig" | None = None,
    ) -> type["ClientConfig"]:
        """Select one configuration namespace and reject ambiguous combinations.

        Exact type matching prevents a parent application's schema, path, or
        environment prefix from silently being used for a child configuration.
        Callers may omit ``config_type`` when passing a configuration instance;
        its concrete type is then the namespace.
        """
        if config_type is not None and (
            not isinstance(config_type, type)
            or not issubclass(config_type, ClientConfig)
        ):
            raise TypeError("config_type must be a ClientConfig subclass.")
        selected = config_type or (type(config) if config is not None else cls)
        if config is not None and type(config) is not selected:
            raise TypeError(
                "config and config_type must have the same concrete ClientConfig type."
            )
        return selected

    def to_dict(self):
        config_dict = self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_defaults=True,
            exclude_unset=True,
        )
        if "auth" in self.model_fields_set:
            # Explicitly selecting default/no authentication is still an override.
            config_dict.setdefault("auth", {})["auth_type"] = self.auth.auth_type
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


def _model_setting_values(
    config_cls: type[ClientConfig], values: dict[str, Any]
) -> dict[str, Any]:
    """Keep dotenv entries that belong to the selected settings schema.

    Unlike ``EnvSettingsSource``, Pydantic's dotenv source exposes unrelated
    entries in a shared `.env` file as extra fields.  Filtering here makes a
    multi-application dotenv file safe when a configuration forbids extras.
    """
    return {
        name: value for name, value in values.items() if name in config_cls.model_fields
    }


def _update_if_not_none(target: dict[str, Any], updates: dict[str, Any]):
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _update_if_not_none(target[key], value)
        else:
            target[key] = value


def _update_config(target: dict[str, Any], updates: dict[str, Any]) -> None:
    """Merge settings, replacing auth whenever its discriminator is supplied."""
    auth_config = updates.get("auth")
    if isinstance(auth_config, dict) and "auth_type" in auth_config:
        target["auth"] = dict(auth_config)
        updates = {key: value for key, value in updates.items() if key != "auth"}
    _update_if_not_none(target, updates)


def _has_config_values(config_kwargs: dict[str, Any]) -> bool:
    """Whether keyword overrides can change the result of a settings merge."""
    return any(value is not None for value in config_kwargs.values())


def _copy_resolved_config(config: ClientConfig) -> ClientConfig:
    """Copy a resolved configuration without replaying its external sources.

    ``BaseModel.model_copy`` retains private attributes, including the source
    path and the auth secret persistor.  Keeping that metadata is essential
    when a CLI-created configuration is wrapped by a Python or app client.
    """
    return config.model_copy(deep=True)


def _set_auth_secret_persistor(config: ClientConfig, config_path: Path) -> None:
    """Persist updated token values to the keyring associated with a config file."""
    config._source_path = config_path

    def persist(auth: AuthConfigBase) -> None:
        save_auth_secrets(
            config_path,
            config.api_url or "",
            auth.auth_type,
            auth.to_secret_dict(),
        )

    config.auth.set_secret_persistor(persist)
