from typing import Optional

import httpx

from .config import AuthConfig


async def login_and_get_token_async(config: AuthConfig) -> Optional[str]:
    """
    Async version of username/password → token.
    Updates config.token in-place.
    """

    if not config.username or not config.password:
        raise ValueError("Username and password must be set for LOGIN auth strategy.")

    url = f"{config.base_url}/auth/login"
    data = {"username": config.username, "password": config.password}

    async with httpx.AsyncClient() as client:
        r = await client.post(url, data=data)
        r.raise_for_status()

        # JSON or plain text token
        try:
            token = r.json().get("token")
        except Exception:
            token = r.text.strip()

        if not token:
            raise RuntimeError("Login succeeded but no token returned.")

        config.token = token
        return token
