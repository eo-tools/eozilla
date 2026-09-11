# Copyright (c) 2025-2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Public configuration prompts and the shared client login/logout workflow."""

from contextlib import closing
from pathlib import Path
from typing import Any

import typer

from cuiman.api.auth.config import (
    AUTH_TYPE_NAMES,
    OAUTH2_GRANT_TYPE_NAMES,
    ApiKeyAuthConfig,
    OAuth2AuthConfig,
    has_credentials,
)
from cuiman.api.auth.secret_store import SecretStoreError
from cuiman.api.client import Client
from cuiman.api.config import ClientConfig
from cuiman.api.defaults import DEFAULT_API_URL, DEFAULT_AUTH_TYPE


def get_config(
    config_path: Path | str | None,
    *,
    require_credentials: bool = True,
    resolve_secrets: bool = True,
) -> ClientConfig:
    """Load an existing profile, optionally allowing login or unreadable secrets."""
    if ClientConfig.from_file(config_path) is None:
        if config_path is None:
            raise ValueError(
                "The client tool has not yet been configured; "
                "please use the 'configure' command to set it up."
            )
        raise ValueError(f"Configuration file {config_path} not found or empty.")
    config = ClientConfig.create(
        config_path=config_path, resolve_secrets=resolve_secrets
    )
    if require_credentials and not has_credentials(config.auth):
        raise ValueError("Please use 'cuiman login' to provide credentials.")
    return config


def configure_client_with_prompt(
    config_path: Path | str | None = None,
    *,
    interactive: bool = True,
    **cli_params: Any,
) -> Path:
    """Collect public provider settings; credentials are collected by login.

    Call directly in a notebook to use its Python input prompts. With
    ``interactive=False``, all prompted settings must be supplied as arguments;
    missing settings raise ``ValueError`` before writing the configuration.
    """
    try:
        previous = ClientConfig.from_file(config_path)
    except ValueError:
        typer.echo(
            "Deprecated or illegal configuration file; configuring from defaults.",
            err=True,
        )
        previous = None
    public = (previous or ClientConfig.default_config).to_file_dict()
    defaults = {"api_url": public.get("api_url") or DEFAULT_API_URL, **public["auth"]}
    supplied = {name: value for name, value in cli_params.items() if value is not None}
    values: dict[str, Any] = {}

    def ask(name: str, label: str, default: Any = "") -> Any:
        value = supplied.get(name)
        if value is None:
            if not interactive:
                option = "scope" if name == "scopes" else name.replace("_", "-")
                raise ValueError(
                    "Interactive configuration requires a terminal. Use a shell or "
                    "JupyterLab terminal, or supply all configuration options. "
                    f"Missing option: --{option}"
                )
            value = typer.prompt(label, default=defaults.get(name) or default)
        values[name] = value
        return value

    ask("api_url", "Process API URL")
    auth_type = _choice(
        ask(
            "auth_type",
            f"Authentication type ({'|'.join(AUTH_TYPE_NAMES)})",
            DEFAULT_AUTH_TYPE,
        ),
        AUTH_TYPE_NAMES,
        "authentication type",
    )
    values["auth_type"] = auth_type
    if auth_type != public["auth"]["auth_type"]:
        # A new auth mechanism must not inherit unrelated provider settings.
        defaults = {"api_url": values["api_url"]}
    if auth_type == "login":
        ask("login_url", "Login URL")
    elif auth_type == "oauth2":
        ask("token_url", "OAuth2 token URL")
        values["grant_type"] = _choice(
            ask(
                "grant_type",
                f"OAuth2 grant type ({'|'.join(OAUTH2_GRANT_TYPE_NAMES)})",
                OAuth2AuthConfig.model_fields["grant_type"].default,
            ),
            OAUTH2_GRANT_TYPE_NAMES,
            "OAuth2 grant type",
        )
    elif auth_type == "oidc":
        ask("issuer_url", "OIDC issuer URL")
    if auth_type in {"oauth2", "oidc"}:
        ask("client_id", "Client ID")
    if auth_type == "oidc":
        defaults["scopes"] = " ".join(
            scope for scope in defaults.get("scopes", ()) if scope != "openid"
        )
        scopes = ask("scopes", "Additional OIDC scopes (space-separated)")
        values["scopes"] = scopes.split() if isinstance(scopes, str) else scopes
    if auth_type in {"token", "login"}:
        values["access_token_header"] = (
            ask("access_token_header", "Custom token header (leave empty for Bearer)")
            or None
        )
    elif auth_type == "api-key":
        ask(
            "api_key_header",
            "API key header",
            ApiKeyAuthConfig.model_fields["api_key_header"].default,
        )
    unused = supplied.keys() - values.keys()
    if unused:
        raise ValueError(
            f"Settings do not apply to {auth_type} authentication: {', '.join(sorted(unused))}."
        )
    api_url = values.pop("api_url")
    config = ClientConfig.new_instance(api_url=api_url, auth=values)
    return config.write(config_path)


def login_client_with_prompt(
    config_path: Path | str | None = None,
    *,
    no_browser: bool = False,
    force: bool = False,
    interactive: bool = True,
) -> None:
    """Prepare and save credentials, prompting only when needed or forced."""
    config = get_config(config_path, require_credentials=False)
    if config.auth.auth_type == "none":
        typer.echo("The configured service does not require login.")
        return
    with closing(Client(config=config)) as client:
        client.login(
            force=force, no_browser=no_browser, interactive=interactive, save=True
        )
    typer.echo("Login completed.")


def logout_client(config_path: Path | str | None = None) -> None:
    """Use the client lifecycle to revoke and remove the profile's credentials."""
    try:
        config = get_config(config_path, require_credentials=False)
    except SecretStoreError:
        config = get_config(
            config_path, require_credentials=False, resolve_secrets=False
        )
    client = Client(config=config, resolve_secrets=False)
    client.logout()
    typer.echo("Logged out.")


def _choice(value: str, choices: tuple[str, ...], label: str) -> str:
    value = value.casefold()
    if value not in choices:
        raise ValueError(
            f"Invalid {label}: {value}. Expected one of: {', '.join(choices)}."
        )
    return value
