from unittest import TestCase

from fastapi.responses import JSONResponse

from wraptile.ap_response import OgcApplicationPackageResponse


class OgcApplicationPackageResponseTest(TestCase):
    def test_subclasses_json_response(self):
        self.assertTrue(issubclass(OgcApplicationPackageResponse, JSONResponse))

    def test_media_type(self):
        self.assertEqual(
            OgcApplicationPackageResponse.media_type, "application/ogcapppkg+json"
        )
