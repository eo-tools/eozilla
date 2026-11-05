#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import abstractmethod
from functools import cached_property
from importlib.util import find_spec
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from cuiman.api.assets import as_stac_asset
from cuiman.api.reader.context import JobResultReadContext
from cuiman.api.reader.reader import JobResultReader

from ._paths import _local_path


class OptionalModuleReader(JobResultReader):
    """Abstract base class for readers that are usable only if
    one or more modules are available in the current Python environment.

    Derived classes must

    - set the `required` class attribute to the names of the
      packages or modules required by the implementing reader.
    - implement the
      [create_implementing_reader][create_implementing_reader] method
      that creates the actual reader implementation reader instance.
    """

    required: tuple[str, ...] = ()
    """The names of module required for the implementing reader."""

    @classmethod
    def is_usable(cls) -> bool:
        """Checks, if all the modules given by
        [required][required] are available.
        """
        return all(find_spec(m) for m in cls.required)

    @classmethod
    def _unavailable_error(cls, ctx: JobResultReadContext) -> Exception | None:
        if "pystac" in cls.required:
            from ._stac.support import unavailable_error

            return unavailable_error(ctx)
        return None

    @cached_property
    def implementing_reader(self):
        """The implementing reader."""
        return self._create_implementing_reader()

    @abstractmethod
    def _create_implementing_reader(self) -> JobResultReader:
        """Create and return the reader implementation."""

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        """Delegates the call to the implementing reader."""
        return await self.implementing_reader.accept_job_result(ctx)

    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        """Delegates the call to the implementing reader."""
        return await self.implementing_reader.read_job_result(ctx)


class PathReader(JobResultReader):
    """
    Abstract base class for job results that use a path-like
    string (path or URL) to reference an output dataset.
    Job result output values are typically modeled as
    `gavicore.models.core.Link` values.
    """

    async def accept_job_result(self, ctx: JobResultReadContext) -> bool:
        path_like = self.get_path_like(ctx)
        if not path_like:
            return False
        data_type = ctx.data_type
        if isinstance(data_type, type) and not self.accept_data_type(data_type):
            return False
        media_type = self.get_media_type(ctx)
        if media_type and not self.accept_media_type(media_type):
            return False
        filename_ext = self.get_filename_ext(path_like)
        if (
            filename_ext
            and (not media_type or as_stac_asset(ctx.value) is None)
            and not self.accept_filename_ext(filename_ext)
        ):
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

    async def read_job_result(self, ctx: JobResultReadContext) -> Any:
        path_or_url = self.get_path_like(ctx)
        assert path_or_url  # from accept() we know we have path_or_url
        filename_ext = self.get_filename_ext(path_or_url)
        media_type = self.get_media_type(ctx)
        return await self.read_path_like(path_or_url, filename_ext, media_type, ctx)

    @abstractmethod
    async def read_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultReadContext,
    ) -> Any:
        """Read the given path or URL."""

    @classmethod
    def get_path_like(cls, ctx: JobResultReadContext) -> str | None:
        """Return the effective location of the context's selected target."""
        if ctx.location and urlsplit(ctx.location).scheme == "file":
            return str(_local_path(ctx.location))
        return ctx.location

    @classmethod
    def get_media_type(cls, ctx: JobResultReadContext) -> str | None:
        """Return the MIME essence for matching; retain parameters in the context."""
        value = ctx.output_media_type
        return value.split(";", 1)[0].strip().lower() if value else value

    @classmethod
    def get_filename_ext(cls, path_like: str):
        """Return a path suffix, excluding a URL's query, fragment, and hostname."""
        path = urlsplit(path_like).path if "://" in path_like else path_like
        return Path(path).suffix
