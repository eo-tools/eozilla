#  Copyright (c) 2026- by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from fastapi.responses import JSONResponse


class OgcApplicationPackageResponse(JSONResponse):
    """Custom response class to correctly incorporate content type in response."""

    media_type = "application/ogcapppkg+json"
