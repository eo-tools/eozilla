#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.util import find_spec
from io import BytesIO
from typing import Any
from urllib.parse import urlsplit

import httpx2
from PIL import Image

from cuiman.api.reader import JobResultReadContext, JobResultReadError

from .base import PathReader


class ImageReaderImpl(PathReader):
    reader_id = "image"
    option_policy = "image"

    def accept_data_type(self, data_type: type) -> bool:
        return data_type is Image.Image

    def accept_media_type(self, media_type: str) -> bool:
        return media_type in Image.MIME.values()

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return filename_ext.lower() in Image.registered_extensions()

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        if ctx.options.get("engine") is not None:
            return False
        if not await super().accept_job_result(ctx):
            return False
        path_like = self.get_path_like(ctx)
        if path_like and path_like.startswith("s3://") and find_spec("s3fs") is None:
            return False
        return True

    async def read_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultReadContext,
    ) -> Any:
        if ctx.options.get("engine") is not None:
            raise JobResultReadError("Pillow does not support engine overrides")
        if urlsplit(path_like).scheme in ("http", "https"):
            async with httpx2.AsyncClient() as client:
                response = await client.get(
                    path_like, follow_redirects=True, timeout=10.0
                )
                response.raise_for_status()
            with Image.open(BytesIO(response.content)) as image:
                return image.copy()
        if path_like.startswith("s3://"):
            import s3fs  # type: ignore[import-not-found]

            storage_options = ctx.options.get("storage_options") or {}
            fs = s3fs.S3FileSystem(**storage_options)
            with fs.open(path_like, "rb") as f:
                # .copy() forces load before the file handle closes (PIL is lazy)
                return Image.open(f).copy()
        return Image.open(path_like)
