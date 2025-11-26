from typing import Optional

import httpx

from .config import AuthConfig


def login_and_get_token(config: AuthConfig) -> Optional[str]:
    """
    Perform login (username+password → token) and update config.token.
    Assumes /auth/login endpoint returning the token either as JSON or plain text.
    """

    if not config.username or not config.password:
        raise ValueError("Username and password must be set for LOGIN auth strategy.")

    url = f"{config.base_url}/auth/login"
    data = {"username": config.username, "password": config.password}

    with httpx.Client() as client:
        r = client.post(url, data=data)
        r.raise_for_status()

        # Accept JSON or plain-text tokens
        token = None
        try:
            token = r.json().get("token")
        except Exception:
            token = r.text.strip()

        if not token:
            raise RuntimeError("Login succeeded but no token returned by server.")

        config.token = token
        return token
