#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import httpx

from .config import AuthConfig


def login_and_get_token(config: AuthConfig) -> str | None:
    """
    Performs login (username+password → token) and updates config.token in-place.

    Args:
        config: authentication configuration.

    Returns:
        An access token either as JSON or plain text.
    """

    if not config.username or not config.password:
        raise ValueError("Username and password must be set for LOGIN auth strategy.")

    data = {"username": config.username, "password": config.password}

    with httpx.Client() as client:
        assert config.auth_url is not None
        r = client.post(config.auth_url, data=data)
        r.raise_for_status()

        # Accept JSON or plain-text tokens
        # noinspection PyBroadException
        try:
            token = r.json().get("token")
        except Exception:
            token = r.text.strip()

        if not token:
            raise RuntimeError("Login succeeded but no token returned by server.")

        config.token = token
        return token
