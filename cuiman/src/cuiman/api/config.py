#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Iterable,
    Optional,
    TypeAlias,
)

import yaml
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    Field,
    HttpUrl,
    PrivateAttr,
    ValidationInfo,
    field_validator,
)
from pydantic_core import PydanticUndefined
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    SettingsConfigDict,
)

from gavicore.models import InputDescription, ProcessDescription, ProcessSummary

from .auth import AuthConfig, AuthConfigBase, AutoAuthConfig
from .auth.config import has_credentials
from .auth.secret_store import load_auth_secrets, save_auth_secrets
from .defaults import DEFAULT_API_URL
from .opener import JobResultOpener, JobResultOpenerRegistry


class ClientConfig(BaseSettings):
    """Client configuration.

    Attributes:
        api_url: a URL pointing to a service compliant with
            the OGC API - Processes.
    """

    model_config = SettingsConfigDict(
        env_prefix="EOZILLA_",
        env_nested_delimiter="__",
        extra="forbid",
        hide_input_in_errors=True,
        dotenv_filtering="match_prefix",
    )

    default_path: ClassVar[Path] = Path("~").expanduser() / ".eozilla" / "config"
    """
    Name of the configuration's local default path. 
    Used for configuration persistence in `~/.<config_name>/`.
    Designed to be overridden by library clients.
    """

    display_name: ClassVar[str | None] = None
    """Application name for notebook labels and app-launch errors.

    Override in an application subclass. When absent, messages use neutral
    wording. This metadata is excluded from settings and saved profiles.
    """

    cli_name: ClassVar[str | None] = None
    """Optional command name for login guidance in the Python API.

    Set only when the application provides a CLI. CLI instances use their own
    ``new_cli(name=...)`` value instead. This metadata is not persisted.
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

    extra_job_result_openers: ClassVar[Iterable[type[JobResultOpener]]] = ()
    """Additional job result opener classes for this application.

    Declare an iterable in a subclass. It is captured as a tuple at class creation
    so generators can be inherited safely. Openers are registered after the
    built-ins, in iteration order, so the last entry is tried first.
    Each class's registry is initialized on first use; later changes should use
    ``register_job_result_opener()``.
    This class attribute is excluded from configuration settings and persistence.
    """

    api_url: Annotated[Optional[str], Field(title="Process API URL")] = DEFAULT_API_URL
    """
    The URL of the server that provides a web API compliant with
    OGC API - Processes, Part 1 - Core. Validated with ``HttpUrl`` but stored
    as a string for consumers that join paths using string operations; an
    empty string or ``None`` means unconfigured.

    This is a base URL: Python and app requests append endpoint paths with
    one slash separator. Both ``/process`` and ``/process/`` therefore use
    ``/process/`` for the landing page and ``/process/processes`` for the
    process list. This joining rule belongs to request construction, not
    validation: ``HttpUrl`` preserves a non-empty path's trailing slash
    and adds ``/`` to a bare host. Authentication endpoint paths instead
    retain their configured trailing slash when making requests.
    """

    auth: AuthConfig = Field(default_factory=AutoAuthConfig)
    """Authentication configuration selected by its ``auth_type`` field.

    Defaults to ``auto``: discover authentication, currently JupyterHub only,
    or use anonymous access if no mechanism is detected. Explicit ``none``
    disables discovery, including in existing profiles.

    When resolving settings with ``create()``, an auth model or a dictionary
    containing ``auth_type`` replaces previous auth settings. A dictionary
    without ``auth_type`` merges into the selected configuration. Matching
    keyring credentials may fill missing secrets after resolution.
    """

    _source_path: Path | None = PrivateAttr(default=None)
    _is_resolved: bool = PrivateAttr(default=False)
    _has_profile: bool = PrivateAttr(default=False)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Give each application independent extension declarations.

        A mutable class attribute would otherwise be shared by an application
        subclass and Cuiman's base configuration.  Copying at class creation
        preserves registrations inherited up to that point while ensuring later
        registrations cannot leak into unrelated client namespaces.
        """
        super().__init_subclass__(**kwargs)
        if "return_type_map" not in cls.__dict__:
            cls.return_type_map = dict(cls.return_type_map)
        cls.extra_job_result_openers = tuple(cls.extra_job_result_openers)

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
        require_file: bool = False,
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

        Fresh settings combine the file, dotenv, process environment, supplied
        config fields, and keyword overrides in that order. Field defaults fill
        missing settings. A resolved ``config`` is a complete snapshot: wrapping
        it, including with overrides, does not reread these external sources.
        An explicitly different ``config_path`` selects a fresh profile instead.
        Secret lookup is independent and can be requested after initially
        resolving with ``resolve_secrets=False``. ``require_file=True`` requires
        an existing, nonempty profile, as the CLI does.
        """
        # 1. Select the application namespace and profile before reading sources.
        #    The chosen class owns the schema, defaults, and settings metadata.
        config_cls = cls._select_config_type(config_type, config)
        source_path = config_cls.normalize_config_path(
            config_path
            if config_path is not None
            else getattr(config, "_source_path", None)
        )
        reuse_snapshot = (
            config is not None
            and config._is_resolved
            and source_path == config._source_path
        )
        # 2. Collect a baseline. A snapshot already includes all source decisions;
        #    a fresh configuration reads each external source exactly once.
        if reuse_snapshot:
            # Defaults and None values are part of a snapshot, even though they
            # would be omitted from an explicit override mapping.
            assert config is not None
            values = config.model_dump(mode="python", round_trip=True)
            has_profile = config._has_profile
        else:
            # Merge from lowest to highest precedence:
            #   file -> dotenv -> process environment -> supplied config fields.
            # Field defaults sit below every source; step 4 fills missing values.
            file_config = config_cls.from_file(source_path)
            has_profile = file_config is not None
            values = {}
            if file_config is not None:
                _update_config(values, file_config.to_dict())
            for source in (
                DotEnvSettingsSource(config_cls),
                EnvSettingsSource(config_cls),
            ):
                _update_config(values, _input_values(config_cls, source()))
            if config is not None:
                supplied = (
                    config.model_dump(mode="python", round_trip=True)
                    if config._is_resolved
                    else config.to_dict()
                )
                _update_config(values, supplied)

        if require_file and not has_profile:
            if config_path is None:
                raise ValueError(
                    "The client tool has not yet been configured; "
                    "please use the 'configure' command to set it up."
                )
            raise ValueError(f"Configuration file {config_path} not found or empty.")

        # 3. Explicit keyword settings have highest precedence, for both fresh
        #    settings and snapshots. Auth selections replace; partial auth merges.
        _update_config(values, _input_values(config_cls, config_kwargs))
        # 4. Validate the combined settings, filling defaults only where needed.
        #    Unchanged snapshots already passed validation and can simply be copied.
        if (
            reuse_snapshot
            and config is not None
            and values == config.model_dump(mode="python", round_trip=True)
        ):
            # Unchanged snapshots already passed validation. Deep copying keeps
            # each client's mutable values independent without rerunning user
            # validators; credential lookup below remains a separate decision.
            resolved = config.model_copy(deep=True)
        else:
            resolved = config_cls._validate_values(
                values, merge_defaults=not reuse_snapshot
            )
        resolved._source_path = source_path
        resolved._has_profile = has_profile
        resolved._is_resolved = True

        # 5. Handle credentials only after the effective service and auth type
        #    are known. Keyring secrets fill missing credentials; they never
        #    override values from any settings source, including class defaults.
        # A persistence hook belongs to a particular profile and authentication
        # configuration. Retain it on unchanged auth, including snapshot copies,
        # but never carry it across an endpoint, profile, or auth override.
        if (
            config is not None
            and source_path == config._source_path
            and resolved.api_url == config.api_url
            and resolved.auth.model_dump() == config.auth.model_dump()
        ):
            resolved.auth = config.auth.model_copy(deep=True)
        if resolve_secrets and has_profile and not has_credentials(resolved.auth):
            _resolve_auth_secrets(resolved, source_path)
        return resolved

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
        config_cls = (
            cls if config_type is None else cls._select_config_type(config_type)
        )
        try:
            config_dict = config_cls.read_file_data(config_path)
            if config_dict is None:
                return None
            # Validate only the file; create() resolves the other settings sources.
            config = config_cls._validate_values(_input_values(config_cls, config_dict))
        except (ValueError, TypeError, yaml.YAMLError):
            raise ValueError(
                "Deprecated or illegal configuration file, please run the 'configure' command."
            ) from None
        config._source_path = config_cls.normalize_config_path(config_path)
        config._has_profile = True
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
        config_cls = (
            cls if config_type is None else cls._select_config_type(config_type)
        )
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
        """Validate supplied values and field defaults without reading sources."""
        config_cls = (
            cls if config_type is None else cls._select_config_type(config_type)
        )
        return config_cls._validate_values(_input_values(config_cls, kwargs))

    @classmethod
    def _validate_values(
        cls, values: dict[str, Any], *, merge_defaults: bool = False
    ) -> "ClientConfig":
        """Validate canonical field names without replaying BaseSettings sources.

        The explicit self instance bypasses BaseSettings.__init__; Pydantic still
        initializes defaults, private attributes, and application validators.
        Input aliases have already been normalized at each source boundary.
        """
        instance = object.__new__(cls)
        cls.__pydantic_validator__.validate_python(
            values,
            self_instance=instance,
            by_alias=True,
            by_name=True,
            context={"partial_default_fields": frozenset(values)}
            if merge_defaults
            else None,
        )
        return instance

    @field_validator("*", mode="before")
    @classmethod
    def _merge_nested_default(cls, value: Any, info: ValidationInfo) -> Any:
        """Fill partial nested defaults during fresh configuration validation.

        The resolver's validation context limits this to fields supplied by its
        merged sources. Missing fields use Pydantic's normal default handling;
        file validation and snapshot overrides never refill application defaults.
        Doing this per field lets factories use validated preceding fields,
        including their defaults, rather than the earlier raw source mapping.
        """
        if (
            not isinstance(value, dict)
            or not info.context
            or info.field_name not in info.context.get("partial_default_fields", ())
        ):
            return value
        assert info.field_name is not None
        field = cls.model_fields[info.field_name]
        if field.is_required() or (info.field_name == "auth" and "auth_type" in value):
            return value
        default = field.get_default(call_default_factory=True, validated_data=info.data)
        if isinstance(default, BaseModel):
            value = _input_values(type(default), value)
            default = default.model_dump(mode="python", round_trip=True)
        if isinstance(default, dict):
            _update_if_not_none(default, value)
            return default
        return value

    @classmethod
    def _select_config_type(
        cls,
        config_type: type["ClientConfig"] | None = None,
        config: "ClientConfig | None" = None,
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

    def to_dict(self) -> dict[str, Any]:
        """Return explicit input fields, retaining values equal to their defaults.

        Nested models are complete selections, including their own defaults.
        In particular, an auth instance always carries its discriminator. This
        mapping is for resolution; ``to_file_dict`` is the secret-free disk format.
        """
        return self.model_dump(
            mode="python",
            round_trip=True,
            include=self.model_fields_set,
            exclude_none=True,
        )

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
        """Validate HTTP URLs as strings; leave base-path joining to consumers.

        Empty values become ``None``. Converting ``HttpUrl`` to ``str`` does
        not strip or append a slash beyond ``HttpUrl``'s own normalization.
        """
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

        Each class starts with the built-ins and its ``extra_job_result_openers``.
        Use it to register further custom openers for special job results.

        Note that the registry contains types/classes, not instances.
        """
        registry = JobResultOpenerRegistry.create_default()
        for opener_type in cls.extra_job_result_openers:
            registry.register(opener_type)
        return registry


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


def _input_values(
    model_type: type[BaseModel], source: dict[str, Any]
) -> dict[str, Any]:
    """Normalize input aliases before comparing precedence across sources.

    Canonical Python names also work as client keyword overrides. Alias choices
    follow Pydantic's declared order; alias paths are read with its public helper.
    No source is validated here, so partial auth remains available for merging.
    Unknown keys survive for the schema's extra policy. The same normalization
    applies when combining a nested model default with an explicit partial value.
    """
    values = dict(source)
    consumed: set[str] = set()
    fields: dict[str, Any] = {}
    for name, field in model_type.model_fields.items():
        alias = field.validation_alias
        aliases = alias.choices if isinstance(alias, AliasChoices) else [alias]
        for candidate in [*aliases, name]:
            if candidate is None:
                continue
            path = (
                candidate if isinstance(candidate, AliasPath) else AliasPath(candidate)
            )
            value = path.search_dict_for_path(source)
            if value is not PydanticUndefined:
                if (
                    isinstance(value, dict)
                    and isinstance(field.annotation, type)
                    and issubclass(field.annotation, BaseModel)
                ):
                    value = _input_values(field.annotation, value)
                fields.setdefault(name, value)
                root = path.path[0]
                assert isinstance(root, str)
                consumed.add(root)
    for name in consumed:
        values.pop(name, None)
    values.update(fields)
    return values


def _update_if_not_none(target: dict[str, Any], updates: dict[str, Any]):
    """Merge partial settings without sharing mutable values with their sources."""
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _update_if_not_none(target[key], value)
        else:
            target[key] = deepcopy(value)


def _update_config(target: dict[str, Any], updates: dict[str, Any]) -> None:
    """Merge settings, replacing auth whenever its discriminator is supplied."""
    auth_config = updates.get("auth")
    if isinstance(auth_config, BaseModel):
        auth_config = auth_config.model_dump(mode="python", round_trip=True)
    if isinstance(auth_config, dict) and "auth_type" in auth_config:
        target["auth"] = deepcopy(auth_config)
        updates = {key: value for key, value in updates.items() if key != "auth"}
    _update_if_not_none(target, updates)


def _resolve_auth_secrets(config: ClientConfig, config_path: Path) -> None:
    """Fill missing credentials after settings resolution, validating only auth.

    Loading secrets must not reconstruct the application settings model: doing
    so would rerun its default factories and validators. Keyring fields are
    filtered to the selected auth type and explicit credentials win.
    """
    secrets = load_auth_secrets(
        config_path, config.api_url or "", config.auth.auth_type
    )
    secrets = {
        name: value
        for name, value in secrets.items()
        if name in config.auth.secret_fields
    }
    if secrets:
        values = {**secrets, **config.auth.model_dump(mode="python", exclude_none=True)}
        config.auth = type(config.auth).model_validate(values)
    _set_auth_secret_persistor(config, config_path)


def _set_auth_secret_persistor(config: ClientConfig, config_path: Path) -> None:
    """Persist updated token values to the keyring associated with a config file."""
    config._source_path = config_path
    # Capture profile identity by value. A copied configuration must not retain
    # a callback whose destination changes when the original config is mutated.
    api_url = config.api_url or ""

    def persist(auth: AuthConfigBase) -> None:
        save_auth_secrets(
            config_path,
            api_url,
            auth.auth_type,
            auth.to_secret_dict(),
        )

    config.auth.set_secret_persistor(persist)
