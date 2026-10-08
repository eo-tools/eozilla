#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import sys
from abc import abstractmethod
from functools import cached_property
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from ..context import JobResultOpenContext
from ..opener import JobResultOpener
from ._paths import _local_path

if TYPE_CHECKING:
    from pystac import Asset


def as_stac_asset(value: Any) -> "Asset | None":
    """Return the value if it is a native PySTAC Asset, otherwise return None.

    Inspect only an already loaded PySTAC module so ordinary result opening
    does not import this optional dependency.
    """
    module = sys.modules.get("pystac")
    asset_type = getattr(module, "Asset", None)
    return value if asset_type is not None and isinstance(value, asset_type) else None


class OptionalModuleOpener(JobResultOpener):
    """Abstract base class for openers that are usable only if
    one or more modules are available in the current Python environment.

    Derived classes must

    - set the `required` class attribute to the names of the
      packages or modules required by the implementing opener.
    - implement the
      [create_implementing_opener][create_implementing_opener] method
      that creates the actual opener implementation opener instance.
    """

    required: tuple[str, ...] = ()
    """The names of module required for the implementing opener."""

    @classmethod
    def is_usable(cls) -> bool:
        """Checks, if all the modules given by
        [required][required] are available.
        """
        return all(find_spec(m) for m in cls.required)

    @classmethod
    def _unavailable_error(cls, ctx: JobResultOpenContext) -> Exception | None:
        if "pystac" in cls.required:
            from ._stac.support import unavailable_error

            return unavailable_error(ctx)
        return None

    @cached_property
    def implementing_opener(self):
        """The implementing opener."""
        return self._create_implementing_opener()

    @abstractmethod
    def _create_implementing_opener(self) -> JobResultOpener:
        """Create and return the opener implementation."""

    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        """Delegates the call to the implementing opener."""
        return await self.implementing_opener.accept_job_result(ctx)

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        """Delegates the call to the implementing opener."""
        return await self.implementing_opener.open_job_result(ctx)


class PathOpener(JobResultOpener):
    """
    Abstract base class for job results that use a path-like
    string (path or URL) to reference an output dataset.
    Job result output values are typically modeled as
    `gavicore.models.Link` values.
    """

    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
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

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        path_or_url = self.get_path_like(ctx)
        assert path_or_url  # from accept() we know we have path_or_url
        filename_ext = self.get_filename_ext(path_or_url)
        media_type = self.get_media_type(ctx)
        return await self.open_path_like(path_or_url, filename_ext, media_type, ctx)

    @abstractmethod
    async def open_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        """Open the given path or URL."""

    @classmethod
    def get_path_like(cls, ctx: JobResultOpenContext) -> str | None:
        """Return the effective location of the context's selected target."""
        if ctx.location and urlsplit(ctx.location).scheme == "file":
            return str(_local_path(ctx.location))
        return ctx.location

    @classmethod
    def get_media_type(cls, ctx: JobResultOpenContext) -> str | None:
        """Return the MIME essence for matching; retain parameters in the context."""
        value = ctx.output_media_type
        return value.split(";", 1)[0].strip().lower() if value else value

    @classmethod
    def get_filename_ext(cls, path_like: str):
        """Return a path suffix, excluding a URL's query, fragment, and hostname."""
        path = urlsplit(path_like).path if "://" in path_like else path_like
        return Path(path).suffix
