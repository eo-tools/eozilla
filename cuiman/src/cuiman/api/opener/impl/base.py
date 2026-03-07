#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Any
from importlib.util import find_spec

from cuiman.api.opener import JobResultOpenContext, JobResultOpener

_PATH_LIKE_KEYS = ("href", "url", "path")
_PATH_LIKE_TYPES = (str, Path)


class OptionalModuleOpener(JobResultOpener):
    """Abstract base class for openers that rely
    on som packages to be available in the current
    Python environment.

    Derived classes must

    - set the `module_names` class attribute
      to the required packages or modules.
    - implement the
      [create_implementing_opener][create_implementing_opener] method
      that creates the actual opener implementation instance..
    """

    module_names: tuple[str, ...] = ()

    def __init__(self, *module_names):
        self.delegate: JobResultOpener | None = None

    @abstractmethod
    def create_implementing_opener(self) -> JobResultOpener:
        """Create the opener implementation."""

    @classmethod
    def is_usable(cls) -> bool:
        """Checks, if all modules in `module_name` are available."""
        return all(find_spec(m) for m in cls.module_names)

    @cached_property
    def implementing_opener(self):
        """The implementing opener."""
        return self.create_implementing_opener()

    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return await self.implementing_opener.accept_job_result(ctx)

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        return await self.implementing_opener.open_job_result(ctx)


class BasePathOpener(JobResultOpener):
    """
    Abstract base class for job results that use a path
    or URL to reference an output dataset.
    Their output values are typically provided as
    `gavicore.models.Link`.
    """

    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        path_or_url = self.get_path_or_url(ctx)
        if not path_or_url:
            return False
        data_type = ctx.data_type
        if isinstance(data_type, type) and not self.accept_data_type(data_type):
            return False
        media_type = ctx.output_media_type
        if media_type and not self.accept_media_type(media_type):
            return False
        filename_ext = self.get_filename_ext(path_or_url)
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

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        path_or_url = self.get_path_or_url(ctx)
        assert path_or_url  # from accept() we know we have path_or_url
        filename_ext = self.get_filename_ext(path_or_url)
        media_type = ctx.output_media_type
        return await self.open_path_or_url(path_or_url, filename_ext, media_type, ctx)

    @abstractmethod
    async def open_path_or_url(
        self,
        path_or_url: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        """Open the given path or URL."""

    @classmethod
    def get_path_or_url(cls, ctx: JobResultOpenContext) -> str | None:
        output_link = ctx.output_link
        if output_link:
            return output_link.href
        output_value = ctx.output_value
        if output_value is not None:
            value = output_value.model_dump()
            if isinstance(value, _PATH_LIKE_TYPES):
                return str(value)
            elif isinstance(value, dict):
                for k in _PATH_LIKE_KEYS:
                    v = value.get(k)
                    if v is not None and isinstance(v, _PATH_LIKE_TYPES):
                        return str(v)
        return None

    @classmethod
    def get_filename_ext(cls, path_or_url: str):
        if "://" in path_or_url:
            path = path_or_url.rsplit("?", maxsplit=1)[0]
        else:
            path = path_or_url
        index = path.rindex(".")
        return path[index:] if index > 0 else ""
