#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Token values returned by authentication protocols, without storage policy."""

from pydantic import BaseModel


class TokenResult(BaseModel):
    """Access and optional refresh tokens returned by an authentication service."""

    access_token: str
    refresh_token: str | None = None
