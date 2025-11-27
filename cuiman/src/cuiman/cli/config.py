#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from pathlib import Path
from typing import Any

import click
import typer

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


def configure_client(
    config_path: Path | str | None = None,
    **cli_params: str | None,
) -> Path:
    prev_params = ClientConfig.create(config_path=config_path).to_dict()
    curr_params: dict[str, str] = {}

    api_url = cli_params.get("api_url")
    if not api_url:
        # TODO: add URL validator
        api_url = typer.prompt(
            "Process API URL",
            default=prev_params.get("api_url") or DEFAULT_API_URL,
        )
        curr_params.update(api_url=api_url)

    auth_type = cli_params.get("auth_type")
    if auth_type is None:
        # TODO: add AuthType validator
        auth_type = typer.prompt(
            f"API authorisation type ({'|'.join(AUTH_TYPE_NAMES)})",
            default=prev_params.get("auth_type") or DEFAULT_AUTH_TYPE,
        )
        curr_params.update(auth_type=auth_type)

    assert bool(api_url)
    assert bool(auth_type)

    if auth_type != "none":
        auth_params = _configure_auth(auth_type, cli_params, prev_params)
        curr_params.update(**auth_params)

    config = ClientConfig.new_instance(**curr_params)
    return config.write(config_path=config_path)


# TODO: Refactor _configure_auth() so that we have exactly one code path
#  for each auth_type. Make reusable prompt_str(), prompt_bool() helpers.


def _configure_auth(
    auth_type: str, cli_params: dict[str, Any], prev_config: dict[str, Any]
) -> dict[str, Any]:
    auth_params: dict[str, Any] = {}

    auth_url: str | None = None
    if auth_type == "login":
        auth_url = cli_params.get("auth_url")
        if auth_url is None:
            # TODO: add URL validator
            auth_url = typer.prompt(
                "Authentication URL",
                default=prev_config.get("auth_url"),
            )
    auth_params.update(auth_url=auth_url)

    if auth_type in ("basic", "login"):
        # TODO: add username validator
        username = cli_params.get("username")
        if username is None:
            username = typer.prompt(
                "Username",
                default=(
                    prev_config.get("username")
                    or os.environ.get("USER", os.environ.get("USERNAME"))
                ),
            )
        auth_params.update(username=username)

        password = cli_params.get("password")
        if password is None:
            prev_password = prev_config.get("password")
            _password = typer.prompt(
                "Password",
                type=str,
                hide_input=True,
                default=_HIDDEN_INPUT if prev_password else None,
            )
            if _password == _HIDDEN_INPUT and prev_password:
                password = prev_password
            else:
                password = _password
        auth_params.update(password=password)

    if auth_type == "token":
        # TODO: add token validator
        token = cli_params.get("token")
        if token is None:
            token = typer.prompt(
                "Access token",
                default=prev_config.get("token"),
            )
        auth_params.update(token=token)

    if auth_type in ("login", "token"):
        # TODO: ask for bearer or custom token header
        pass

    if auth_type == "login":
        assert bool(auth_url)
        auth_config = AuthConfig(**auth_params)
        token = login(auth_config)
        auth_params.update(token=token)

    return auth_params
