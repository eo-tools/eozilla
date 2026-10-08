#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import xarray as xr

from ...context import JobResultContext
from ...resources import JobResultResource
from .base import PathOpener


class XarrayDatasetOpenerImpl(PathOpener):
    """Xarray adapter for the selected dataset and effective backend settings."""

    def accept_data_type(self, data_type: type) -> bool:
        return data_type is xr.Dataset

    def accept_media_type(self, media_type: str) -> bool:
        return True

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return True

    async def open_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        resource: JobResultResource,
        context: JobResultContext,
    ) -> Any:
        """Read this dataset using scoped storage options under backend_kwargs."""
        # Use xarray's generic read function
        return xr.open_dataset(
            path_like, **await context.reader_options(resource, storage_in_backend=True)
        )
