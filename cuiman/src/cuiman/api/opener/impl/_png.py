#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from PIL import Image

from cuiman.api.opener import JobResultOpenContext, JobResultOpenError

from .base import PathOpener


class PngImageOpenerImpl(PathOpener):
    def accept_data_type(self, data_type: type) -> bool:
        return data_type is Image.Image

    def accept_media_type(self, media_type: str) -> bool:
        return media_type == "image/png"

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return filename_ext.lower() == ".png"

    async def open_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        if path_like.startswith("s3://"):
            try:
                import s3fs
            except ImportError as e:
                raise JobResultOpenError(
                    "s3fs is required to open PNG files from S3"
                ) from e
            storage_options = ctx.options.get("storage_options", {})
            fs = s3fs.S3FileSystem(**storage_options)
            with fs.open(path_like, "rb") as f:
                # .copy() forces load before the file handle closes (PIL is lazy)
                return Image.open(f).copy()
        return Image.open(path_like)
