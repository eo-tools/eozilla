#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.util import find_spec
from typing import Any

from PIL import Image

from ...context import JobResultContext
from ...resources import JobResultResource
from .base import PathOpener


class ImageOpenerImpl(PathOpener):
    """Pillow image adapter with optional S3 storage support."""

    def accept_data_type(self, data_type: type) -> bool:
        return data_type is Image.Image

    def accept_media_type(self, media_type: str) -> bool:
        return media_type in Image.MIME.values()

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return filename_ext.lower() in Image.registered_extensions()

    async def accept(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> bool:
        """Check image metadata and required storage dependencies without reading."""
        if not await super().accept(resource, context=context):
            return False
        path_like = self.get_path_like(resource)
        if path_like and path_like.startswith("s3://") and find_spec("s3fs") is None:
            return False
        return True

    async def open_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        resource: JobResultResource,
        context: JobResultContext,
    ) -> Any:
        """Read an image, acquiring S3 access only for a selected S3 target."""
        options = dict(context.options)
        options.pop("storage_options", None)
        if path_like.startswith("s3://"):
            import s3fs  # type: ignore[import-not-found]

            storage_options = (await context.reader_options(resource)).get(
                "storage_options", {}
            )
            fs = s3fs.S3FileSystem(**storage_options)
            with fs.open(path_like, "rb") as f:
                # .copy() forces load before the file handle closes (PIL is lazy)
                return Image.open(f, **options).copy()
        return Image.open(path_like, **options)
