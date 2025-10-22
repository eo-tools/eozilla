#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from pathlib import Path

import click
import typer

from s2gos_client.api.config import ClientConfig
from s2gos_client.api.defaults import DEFAULT_SERVER_URL


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
    user_name: str | None = None,
    access_token: str | None = None,
    server_url: str | None = None,
    config_path: Path | str | None = None,
) -> Path:
    config = ClientConfig.create(config_path=config_path)
    if not user_name:
        user_name = typer.prompt(
            "User name",
            default=(
                (config and config.user_name)
                or os.environ.get("USER", os.environ.get("USERNAME"))
            ),
        )
    if not access_token:
        prev_access_token = config and config.access_token
        _access_token = typer.prompt(
            "Access token",
            type=str,
            hide_input=True,
            default="*****" if prev_access_token else None,
        )
        if _access_token == "*****" and prev_access_token:
            access_token = prev_access_token
        else:
            access_token = _access_token
    if not server_url:
        server_url = typer.prompt(
            "Server URL",
            default=(config and config.server_url) or DEFAULT_SERVER_URL,
        )
    return ClientConfig(
        user_name=user_name, access_token=access_token, server_url=server_url
    ).write(config_path=config_path)
