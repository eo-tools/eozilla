#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from pathlib import Path
from typing import Any

import click
import typer

from cuiman.api.auth import AuthType
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
    api_url: str | None = None,
    auth_type: AuthType | None = None,
    config_path: Path | str | None = None,
) -> Path:
    _no_default = 10 * "*"
    config = ClientConfig.create(config_path=config_path)
    if not api_url:
        api_url = typer.prompt(
            "Process API URL",
            default=(config and config.api_url) or DEFAULT_API_URL,
        )
    if not auth_type or auth_type == AuthType.NONE:
        auth_type = typer.prompt(
            "API authorisation type",
            default=(config and config.auth_type) or DEFAULT_AUTH_TYPE,
            type=click.Choice([e.value for e in AuthType]),
        )
    auth_config: dict[str, Any] = {}
    if auth_type in (AuthType.BASIC, AuthType.TOKEN, AuthType.LOGIN):
        auth_config.update(auth_type=auth_type)
        # ----------------------
        # username
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
        prev_password = config and config.password
        _password = typer.prompt(
            "Password",
            type=str,
            hide_input=True,
            default=_no_default if prev_password else None,
        )
        if _password == _no_default and prev_password:
            password = prev_password
        else:
            password = _password
        auth_config.update(password=password)

    return ClientConfig(api_url=api_url, **auth_config).write(config_path=config_path)
