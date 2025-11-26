#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from pathlib import Path
from typing import Any

import click
import typer

from cuiman.api.auth import AuthType
from cuiman.api.auth.config import AUTH_TYPE_NAMES
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


def configure_client(
    config_path: Path | str | None = None,
    api_url: str | None = None,
    auth_type: AuthType | None = None,
    auth_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    token: str | None = None,
) -> Path:
    _hidden_input = 6 * "*"
    config = ClientConfig.create(config_path=config_path)
    if not api_url:
        api_url = typer.prompt(
            "Process API URL",
            default=(config and config.api_url) or DEFAULT_API_URL,
        )
    if auth_type is None:
        auth_type = typer.prompt(
            f"API authorisation type ({'|'.join(AUTH_TYPE_NAMES)})",
            default=(config and config.auth_type) or DEFAULT_AUTH_TYPE,
        )

    # TODO: refactor me, extract configure_auth()
    auth_config: dict[str, Any] = {}
    if auth_type is not None:
        auth_config.update(auth_type=auth_type)

    if auth_type == "login":
        if auth_url is None:
            auth_url = typer.prompt(
                "Authentication URL",
                default=config and config.auth_url,
            )
        auth_config.update(auth_url=auth_url)

    if auth_type in ("basic", "login"):
        auth_config.update(auth_type=auth_type)
        # ----------------------
        # username
        # ----------------------
        if username is None:
            username = typer.prompt(
                "Username",
                default=(
                    (config and config.username)
                    or os.environ.get("USER", os.environ.get("USERNAME"))
                ),
            )
            auth_config.update(username=username)
        # ----------------------
        # password
        # ----------------------
        if password is None:
            prev_password = config and config.password
            _password = typer.prompt(
                "Password",
                type=str,
                hide_input=True,
                default=_hidden_input if prev_password else None,
            )
            if _password == _hidden_input and prev_password:
                password = prev_password
            else:
                password = _password
            auth_config.update(password=password)
    if auth_type == "token":
        # ----------------------
        # token
        # ----------------------
        if token is None:
            token = typer.prompt(
                "Access token",
                default=config and config.token,
            )
            auth_config.update(token=token)
    # TODO: ask for bearer or custom token header
    return ClientConfig(api_url=api_url, **auth_config).write(config_path=config_path)
