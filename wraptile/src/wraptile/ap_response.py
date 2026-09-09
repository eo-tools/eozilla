from fastapi.responses import JSONResponse


class OgcApplicationPackageResponse(JSONResponse):
    """Custom response class to correctly incorporate content type in response."""

    media_type = "application/ogcapppkg+json"
