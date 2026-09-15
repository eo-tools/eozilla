#  Copyright (c) 2026- by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

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
