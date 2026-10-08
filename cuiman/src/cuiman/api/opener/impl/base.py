#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import abstractmethod
from collections.abc import Mapping
from functools import cached_property
from importlib.util import find_spec
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from urllib.request import url2pathname

from ...context import JobResultContext
from ...resources import JobResultResource
from ..opener import JobResultOpener


class OptionalModuleOpener(JobResultOpener):
    """Expose a reader without requiring its optional dependency at import time.

    The registry can list this opener even when the reader is absent. Dispatch
    checks its required modules and imports the concrete adapter only on use.
    """

    required: tuple[str, ...] = ()
    """Modules required by the implementing opener."""

    @classmethod
    def is_usable(cls) -> bool:
        """Whether every declared optional reader module is available."""
        return all(find_spec(module) for module in cls.required)

    @cached_property
    def implementing_opener(self) -> JobResultOpener:
        """Reader adapter, initialized only when this candidate is used."""
        return self._create_implementing_opener()

    @abstractmethod
    def _create_implementing_opener(self) -> JobResultOpener:
        """Create the concrete reader adapter."""

    async def accept(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> bool:
        """Check the concrete adapter without reading a payload."""
        return await self.implementing_opener.accept(resource, context=context)

    async def open(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> Any:
        """Open through the concrete reader adapter."""
        return await self.implementing_opener.open(resource, context=context)


class PathOpener(JobResultOpener):
    """Share target extraction and format checks among file-based readers.

    Subclasses supply supported formats, return types, and the actual read.
    This base handles the selected link or path-like value consistently without
    consulting original-output provenance or probing storage during acceptance.
    """

    async def accept(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> bool:
        """Check selected location, requested type, format, and filename extension."""
        path = self.get_path_like(resource)
        if not path:
            return False
        if context.data_type is not None and not self.accept_data_type(
            context.data_type
        ):
            return False
        media_type = context.media_type_for(resource)
        if media_type and not self.accept_media_type(
            media_type.partition(";")[0].strip().lower()
        ):
            return False
        extension = self.get_filename_ext(path)
        return not extension or self.accept_filename_ext(extension)

    @abstractmethod
    def accept_media_type(self, media_type: str) -> bool:
        """Whether the normalized base media type is supported."""

    @abstractmethod
    def accept_filename_ext(self, filename_ext: str) -> bool:
        """Whether the filename extension is supported."""

    @abstractmethod
    def accept_data_type(self, data_type: type) -> bool:
        """Whether this adapter returns the requested Python type."""

    async def open(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> Any:
        """Read the selected target using runtime settings and scoped storage access."""
        path = self.get_path_like(resource)
        assert path
        return await self.open_path_like(
            path,
            self.get_filename_ext(path),
            context.media_type_for(resource),
            resource,
            context,
        )

    @abstractmethod
    async def open_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        resource: JobResultResource,
        context: JobResultContext,
    ) -> Any:
        """Adapt a normalized selected location to the concrete reader library.

        The base has extracted the path and format; implementations use the
        context to obtain effective options and any required storage access.
        """

    @classmethod
    def get_path_like(cls, resource: JobResultResource) -> str | None:
        """Extract only the selected target, never a provenance link or schema."""
        value: Any = resource.link.href if resource.link else resource.value
        if isinstance(value, Mapping) and "mediaType" in value and "value" in value:
            value = value["value"]
        if isinstance(value, Mapping):
            value = next(
                (
                    value[key]
                    for key in ("href", "url", "path")
                    if isinstance(value.get(key), str)
                ),
                None,
            )
        if not isinstance(value, str):
            return None
        if value.startswith("file:"):
            parts = urlsplit(value)
            value = url2pathname(
                (
                    "//" + parts.netloc
                    if parts.netloc and parts.netloc != "localhost"
                    else ""
                )
                + parts.path
            )
        return value

    @classmethod
    def get_filename_ext(cls, path_like: str) -> str:
        """Filename suffix without URL query/fragment or directory dots."""
        path = (
            urlsplit(path_like).path
            if "://" in path_like
            else path_like.replace("\\", "/")
        )
        return PurePosixPath(path).suffix.lower()
