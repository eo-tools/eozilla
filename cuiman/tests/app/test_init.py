#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import cuiman.app as app
from cuiman.app.serve import serve
from cuiman.app.store import create_app_remote_store


def test_app_exports():
    assert app.__all__ == ["create_app_remote_store", "serve"]
    assert app.create_app_remote_store is create_app_remote_store
    assert app.serve is serve
