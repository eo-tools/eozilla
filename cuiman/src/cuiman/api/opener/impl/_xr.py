#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import xarray as xr

from cuiman.api.opener import JobResultOpenContext

from .base import BasePathOpener


class XarrayDatasetOpenerImpl(BasePathOpener):
    def accept_data_type(self, data_type: type) -> bool:
        return data_type is xr.Dataset

    def accept_media_type(self, media_type: str) -> bool:
        return True

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return True

    async def open_path_or_url(
        self,
        path_or_url: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        # Use xarray's generic read function
        return xr.open_dataset(path_or_url, **ctx.options)
