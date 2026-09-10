#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""CLI helpers for public configuration and OS-backed authentication secrets."""

from pathlib import Path
from typing import Any, cast

import typer
from pydantic import BaseModel

from cuiman.api.auth import (
    NoAuthConfig,
)
from cuiman.api.auth.config import (
    AUTH_TYPE_NAMES,
    OAUTH2_GRANT_TYPE_NAMES,
    OAuth2GrantType,
    has_credentials,
)
from cuiman.api.auth.secret_store import SecretStoreError
from cuiman.api.client import Client
from cuiman.api.config import ClientConfig
from cuiman.api.defaults import DEFAULT_API_URL, DEFAULT_AUTH_TYPE


def get_config(config_path: Path | str | None) -> ClientConfig:
    """Load the configured client, resolving matching keyring credentials."""
    file_config = ClientConfig.from_file(config_path=config_path)
    if file_config is None:
        if config_path is None:
            raise ValueError(
                "The client tool has not yet been configured; "
                "please use the 'configure' command to set it up."
            )
        raise ValueError(f"Configuration file {config_path} not found or empty.")
    config = ClientConfig.create(config_path=config_path)
    _ensure_cli_credentials(config)
    return config


class _Context(BaseModel):
    """Values used while prompting for public configuration settings."""

    cli_params: dict[str, Any]
    prev_params: dict[str, Any]
    curr_params: dict[str, Any]


def configure_client_with_prompt(
    config_path: Path | str | None = None,
    **cli_params: Any,
) -> Path:
    """Prompt for public configuration values and write them to a file."""
    previous = _get_previous_public_config(config_path)
    previous_auth = previous.pop("auth", {})
    ctx = _Context(
        cli_params=cli_params,
        prev_params={**previous, **previous_auth},
        curr_params={},
    )

    _prompt_for_str(ctx, "api_url", "Process API URL", DEFAULT_API_URL)
    auth_type = _prompt_for_auth_type(ctx)
    if auth_type != "none":
        _configure_public_auth_with_prompt(ctx, auth_type)

    config = ClientConfig.new_instance(
        api_url=ctx.curr_params["api_url"],
        auth=_current_auth_params(ctx),
    )
    return config.write(config_path=config_path)


def login_client_with_prompt(
    config_path: Path | str | None = None,
    *,
    no_browser: bool = False,
) -> None:
    """Prompt for credentials, authenticate when needed, and save them securely."""
    config = _get_login_config(config_path)
    auth = config.auth
    if isinstance(auth, NoAuthConfig):
        typer.echo("The configured service does not require login.")
        return
    client = Client(
        config=config, config_path=str(config_path) if config_path else None
    )
    try:
        client.login(force=True, no_browser=no_browser, save=True)
    finally:
        client.close()
    typer.echo("Login completed.")


def logout_client(config_path: Path | str | None = None) -> None:
    """Remove locally stored credentials for the configured service."""
    try:
        config = _get_login_config(config_path)
    except SecretStoreError:
        config = _get_login_config(config_path, resolve_secrets=False)
    client = Client(
        config=config,
        config_path=str(config_path) if config_path else None,
        resolve_secrets=False,
    )
    client.logout()
    typer.echo("Logged out.")


def _configure_public_auth_with_prompt(ctx: _Context, auth_type: str) -> None:
    if auth_type == "login":
        _prompt_for_str(ctx, "login_url", "Login URL", "")
        _configure_token_type_with_prompt(ctx)
    elif auth_type == "oauth2":
        _prompt_for_str(ctx, "token_url", "OAuth2 token URL", "")
        _prompt_for_oauth2_grant_type(ctx)
        _prompt_for_str(ctx, "client_id", "OAuth2 client ID", "")
    elif auth_type == "oidc":
        _prompt_for_str(ctx, "issuer_url", "OIDC issuer URL", "")
        _prompt_for_str(ctx, "client_id", "OIDC client ID", "")
        _prompt_for_scopes(ctx)
    elif auth_type == "token":
        _configure_token_type_with_prompt(ctx)
    elif auth_type == "api-key":
        _prompt_for_str(ctx, "api_key_header", "Access key header", "X-API-Key")


def _configure_token_type_with_prompt(ctx: _Context) -> None:
    use_bearer = _prompt_for_bool(ctx, "use_bearer", "Use bearer token?", True)
    if not use_bearer:
        _prompt_for_str(
            ctx,
            "access_token_header",
            "Access token header",
            "X-Auth-Token",
        )


def _current_auth_params(ctx: _Context) -> dict[str, Any]:
    return {key: value for key, value in ctx.curr_params.items() if key != "api_url"}


def _get_previous_public_config(config_path: Path | str | None) -> dict[str, Any]:
    config_data = ClientConfig.read_file_data(config_path)
    if config_data is None:
        return ClientConfig.default_config.to_file_dict()
    try:
        config = ClientConfig.from_file(config_path)
    except ValueError as exc:
        if not str(exc).startswith("Legacy configuration format detected"):
            raise
        typer.echo(
            "Warning: legacy configuration detected; saved credentials will be "
            "discarded when configuration is rewritten.",
            err=True,
        )
        return _get_public_legacy_config(config_data)
    assert config is not None
    return config.to_file_dict()


def _ensure_cli_credentials(config: ClientConfig) -> None:
    if not has_credentials(config.auth):
        raise ValueError("Please use 'cuiman login' to provide credentials.")


def _get_public_legacy_config(config_data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(config_data.get("auth"), dict):
        auth_data = dict(config_data["auth"])
        auth_type = auth_data.get("auth_type", "none")
        config = {key: value for key, value in config_data.items() if key != "auth"}
    else:
        auth_type = config_data.get("auth_type", "none")
        auth_data = config_data
        config = {
            key: value
            for key, value in config_data.items()
            if key
            not in {
                "api_key",
                "api_key_header",
                "auth_type",
                "auth_url",
                "client_id",
                "client_secret",
                "grant_type",
                "password",
                "refresh_token",
                "token",
                "token_header",
                "use_bearer",
                "username",
            }
        }

    public_auth: dict[str, Any] = {"auth_type": auth_type}
    if auth_type == "login":
        _copy_if_present(public_auth, auth_data, "login_url", "auth_url")
    elif auth_type == "oauth2":
        _copy_if_present(public_auth, auth_data, "token_url", "auth_url")
        _copy_if_present(public_auth, auth_data, "grant_type", "grant_type")
        _copy_if_present(public_auth, auth_data, "client_id", "client_id")
    if auth_type in {"login", "oauth2", "token"}:
        _copy_if_present(public_auth, auth_data, "use_bearer", "use_bearer")
        _copy_if_present(public_auth, auth_data, "access_token_header", "token_header")
    if auth_type == "api-key":
        _copy_if_present(public_auth, auth_data, "api_key_header", "api_key_header")
    return {**config, "auth": public_auth}


def _copy_if_present(
    target: dict[str, Any], source: dict[str, Any], target_key: str, *source_keys: str
) -> None:
    for source_key in (target_key, *source_keys):
        if source_key in source:
            target[target_key] = source[source_key]
            return


def _get_login_config(
    config_path: Path | str | None, *, resolve_secrets: bool = True
) -> ClientConfig:
    file_config = ClientConfig.from_file(config_path)
    if file_config is None:
        if config_path is None:
            raise ValueError(
                "The client tool has not yet been configured; "
                "please use the 'configure' command to set it up."
            )
        raise ValueError(f"Configuration file {config_path} not found or empty.")
    return ClientConfig.create(config_path=config_path, resolve_secrets=resolve_secrets)


def _prompt_for_auth_type(ctx: _Context) -> str:
    previous_auth_type = ctx.prev_params.get("auth_type")
    default_auth_type = (
        previous_auth_type.casefold()
        if isinstance(previous_auth_type, str)
        and previous_auth_type.casefold() in AUTH_TYPE_NAMES
        else DEFAULT_AUTH_TYPE
    )
    auth_type = ctx.cli_params.get("auth_type")
    if auth_type is None:
        auth_type = (
            typer.prompt(
                f"API authorisation type ({'|'.join(AUTH_TYPE_NAMES)})",
                type=str,
                default=default_auth_type,
            )
            or ""
        )
    auth_type = auth_type.casefold()
    ctx.curr_params["auth_type"] = auth_type
    if auth_type not in AUTH_TYPE_NAMES:
        raise ValueError(
            f"Invalid authentication type: {auth_type}. "
            f"Expected one of: {', '.join(AUTH_TYPE_NAMES)}."
        )
    return auth_type


def _prompt_for_oauth2_grant_type(ctx: _Context) -> OAuth2GrantType:
    grant_type = _prompt_for_str(
        ctx,
        "grant_type",
        f"OAuth2 grant type ({'|'.join(OAUTH2_GRANT_TYPE_NAMES)})",
        "password",
    ).casefold()
    if grant_type not in OAUTH2_GRANT_TYPE_NAMES:
        raise ValueError(
            f"Invalid OAuth2 grant type: {grant_type}. "
            f"Expected one of: {', '.join(OAUTH2_GRANT_TYPE_NAMES)}."
        )
    return cast(OAuth2GrantType, grant_type)


def _prompt_for_scopes(ctx: _Context) -> None:
    """Collect optional OIDC resource scopes without persisting secret values."""
    scopes = ctx.cli_params.get("scopes")
    if scopes is None:
        previous_scopes = ctx.prev_params.get("scopes", [])
        default = (
            " ".join(previous_scopes)
            if isinstance(previous_scopes, (list, tuple))
            else ""
        )
        scopes = (
            typer.prompt("OIDC scopes (space-separated)", default=default) or ""
        ).split()
    ctx.curr_params["scopes"] = scopes


def _prompt_for_str(ctx: _Context, key: str, text: str, default: str) -> str:
    value: str | None = ctx.cli_params.get(key)
    if value is None:
        value = (
            typer.prompt(
                text,
                type=str,
                default=ctx.prev_params.get(key) or default,
            )
            or ""
        )
    ctx.curr_params[key] = value
    return value


def _prompt_for_bool(
    ctx: _Context,
    key: str,
    text: str,
    default: bool,
) -> bool:
    value: bool | None = ctx.cli_params.get(key)
    if value is None:
        value = typer.confirm(text, default=ctx.prev_params.get(key, default))
    ctx.curr_params[key] = value
    return value
