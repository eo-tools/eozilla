#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import abstractmethod
from pathlib import Path
from typing import Any

from cuiman.api.opener import JobResultOpenContext, JobResultOpener

_PATH_LIKE_KEYS = ("href", "url", "path")
_PATH_LIKE_TYPES = (str, Path)


class PathOrUrlOpener(JobResultOpener):
    """
    Abstract base class for job results that use a path
    or URL to reference an output dataset.
    """

    async def accept(self, ctx: JobResultOpenContext) -> bool:
        path_or_url = get_path_or_url(ctx)
        if not path_or_url:
            return False
        data_type = ctx.data_type
        if isinstance(data_type, type) and not self.accept_data_type(data_type):
            return False
        media_type = ctx.output_media_type
        if media_type and not self.accept_media_type(media_type):
            return False
        filename_ext = get_filename_ext(path_or_url)
        if filename_ext and not self.accept_filename_ext(filename_ext):
            return False
        return True

    @abstractmethod
    def accept_media_type(self, media_type: str) -> bool:
        """Check whether given media type (MIME-type) is accepted."""

    @abstractmethod
    def accept_filename_ext(self, filename_ext: str) -> bool:
        """Check whether given filename extension is accepted."""

    @abstractmethod
    def accept_data_type(self, data_type: type) -> bool:
        """Check whether given data type is accepted."""

    async def open(self, ctx: JobResultOpenContext) -> Any:
        path_or_url = get_path_or_url(ctx)
        assert path_or_url  # from accept() we know we have path_or_url
        filename_ext = get_filename_ext(path_or_url)
        media_type = ctx.output_media_type
        return self.open_path_or_url(path_or_url, filename_ext, media_type, ctx)

    @abstractmethod
    async def open_path_or_url(
        self,
        path_or_url: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        """Open the given path or URL."""


def get_path_or_url(ctx: JobResultOpenContext) -> str | None:
    if ctx.output_link:
        return ctx.output_link.href
    output_value = ctx.output_value.model_dump()
    if isinstance(output_value, _PATH_LIKE_TYPES):
        return str(output_value)
    elif isinstance(output_value, dict):
        for k in _PATH_LIKE_KEYS:
            v = output_value.get(k)
            if v is not None and isinstance(v, _PATH_LIKE_TYPES):
                return str(v)
    return None


def get_filename_ext(path_or_url: str):
    if "://" in path_or_url:
        path = path_or_url.rsplit("?", maxsplit=1)[0]
    else:
        path = path_or_url
    index = path.rindex(".")
    return path[index:] if index > 0 else ""
