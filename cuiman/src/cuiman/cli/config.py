#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from pathlib import Path
from typing import Any

import click
import typer
from pydantic import BaseModel

from cuiman.api.auth import login
from cuiman.api.auth.config import AUTH_TYPE_NAMES, AuthConfig
from cuiman.api.config import ClientConfig
from cuiman.api.defaults import DEFAULT_API_URL, DEFAULT_AUTH_TYPE


def get_config(config_path: Path | str | None) -> ClientConfig:
    file_config = ClientConfig.from_file(config_path=config_path)
    if file_config is None:
        if config_path is None:
            raise click.ClickException(
                "The client tool has not yet been configured;"
                " please use the 'configure' command to set it up."
            )
        else:
            raise click.ClickException(
                f"Configuration file {config_path} not found or empty."
            )
    return ClientConfig.create(config=file_config)


_HIDDEN_INPUT = 6 * "*"


class _Context(BaseModel):
    cli_params: dict[str, Any]
    prev_params: dict[str, Any]
    curr_params: dict[str, Any]


def configure_client_with_prompt(
    config_path: Path | str | None = None,
    **cli_params: str | bool | None,
) -> Path:
    ctx = _Context(
        cli_params=cli_params,
        prev_params=ClientConfig.create(config_path=config_path).to_dict(),
        curr_params={},
    )

    # TODO: add URL validator
    _prompt_for_str(ctx, "api_url", "Process API URL", DEFAULT_API_URL)
    auth_type = _prompt_for_str(
        ctx,
        "auth_type",
        "API authorisation type",
        DEFAULT_AUTH_TYPE,
        choice=click.Choice(AUTH_TYPE_NAMES, case_sensitive=False),
    )
    if auth_type and auth_type != "none":
        _configure_auth_with_prompt(ctx, auth_type)

    config = ClientConfig.new_instance(**ctx.curr_params)
    return config.write(config_path=config_path)


def _configure_auth_with_prompt(ctx: _Context, auth_type: str) -> None:
    if auth_type == "basic":
        _configure_basic_auth_with_prompt(ctx)
    elif auth_type == "login":
        _configure_login_auth_with_prompt(ctx)
    elif auth_type == "token":
        _configure_token_auth_with_prompt(ctx)
    elif auth_type == "api-key":
        _configure_api_key_auth_with_prompt(ctx)


def _configure_basic_auth_with_prompt(ctx: _Context) -> None:
    _configure_username_password_with_prompt(ctx)


def _configure_login_auth_with_prompt(ctx: _Context) -> None:
    # TODO: add URL validator
    _prompt_for_str(ctx, "auth_url", "Authentication URL", "")
    _prompt_for_str(ctx, "client_id", "OAuth2 client ID", "")
    _prompt_for_pw(ctx, "client_secret", "OAuth2 client secret")
    _configure_username_password_with_prompt(ctx)
    auth_config = AuthConfig(**ctx.curr_params)
    ctx.curr_params["token"] = login(auth_config)
    _configure_token_type_with_prompt(ctx)


def _configure_token_auth_with_prompt(ctx: _Context) -> None:
    _prompt_for_str(ctx, "token", "API access token", "")
    _configure_token_type_with_prompt(ctx)


def _configure_api_key_auth_with_prompt(ctx: _Context) -> None:
    _prompt_for_str(ctx, "api_key", "API access key", "")
    _prompt_for_str(ctx, "api_key_header", "Access key header", "X-API-Key")


def _configure_username_password_with_prompt(ctx: _Context) -> None:
    _prompt_for_str(
        ctx,
        "username",
        "Username",
        os.environ.get("USER") or os.environ.get("USERNAME") or "",
    )
    _prompt_for_pw(ctx, "password", "Password")


def _configure_token_type_with_prompt(ctx: _Context) -> None:
    use_bearer = _prompt_for_bool(ctx, "use_bearer", "Use bearer token?", False)
    if not use_bearer:
        _prompt_for_str(ctx, "token_header", "Access token header", "X-Auth-Token")


def _prompt_for_str(
    ctx: _Context, key: str, text: str, default: str, choice: click.Choice | None = None
) -> str:
    value: str | None = ctx.cli_params.get(key)
    if value is None:
        value = (
            typer.prompt(
                text,
                type=choice or str,
                default=ctx.prev_params.get(key) or default,
            )
            or ""
        )
    ctx.curr_params.update({key: value})
    assert isinstance(value, str)
    return value


def _prompt_for_pw(
    ctx: _Context,
    key: str,
    text: str,
) -> str:
    pw = ctx.cli_params.get(key)
    if pw is None:
        prev_pw: str | None = ctx.prev_params.get(key)
        new_pw: str = typer.prompt(
            text,
            type=str,
            hide_input=True,
            default=_HIDDEN_INPUT if prev_pw else None,
        )
        if new_pw == _HIDDEN_INPUT and prev_pw:
            pw = prev_pw
        else:
            pw = new_pw
    ctx.curr_params.update({key: pw})
    assert isinstance(pw, str)
    return pw


def _prompt_for_bool(
    ctx: _Context,
    key: str,
    text: str,
    default: bool,
) -> bool:
    value: bool | None = ctx.cli_params.get(key)
    if value is None:
        value = typer.confirm(
            text,
            default=ctx.prev_params.get(key) or default,
        )
    ctx.curr_params.update({key: value})
    assert isinstance(value, bool)
    return value
