# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Warning categories shared by Cuiman's Python API and lightweight CLI."""


class SecretStoreFallbackWarning(RuntimeWarning):
    """Credentials are stored only in memory because no keyring is available."""
