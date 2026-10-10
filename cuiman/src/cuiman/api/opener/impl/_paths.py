# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Local path conversion shared by result openers."""

import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from cuiman.api.opener.errors import JobResultOpenError


def _local_path(source: str) -> Path:
    parsed = urlsplit(source)
    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc != "localhost":
            if os.name != "nt":
                raise JobResultOpenError(
                    "Remote file URI is unsupported on this platform"
                )
            return Path(f"//{parsed.netloc}{url2pathname(parsed.path)}")
        return Path(url2pathname(parsed.path))
    if parsed.scheme and not (os.name == "nt" and len(parsed.scheme) == 1):
        raise JobResultOpenError("Local path URI scheme is unsupported")
    return Path(source)
