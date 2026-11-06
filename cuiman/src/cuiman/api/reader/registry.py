#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable, TypeAlias

from .reader import JobResultReader, assert_reader_type_valid

JobResultReaderType: TypeAlias = type[JobResultReader]
"""A concrete job result reader class."""


class JobResultReaderRegistry:
    """A simple registry for job result readers."""

    def __init__(self):
        self._reader_types: list[JobResultReaderType] = []

    @classmethod
    def create_default(cls) -> "JobResultReaderRegistry":
        """Create a registry that includes default job result readers."""
        from .impl import (
            GeopandasDataFrameReader,
            ImageReader,
            PandasDataFrameReader,
            StacJobResultReader,
            XarrayDatasetReader,
        )

        registry = cls()
        registry.register(GeopandasDataFrameReader)
        registry.register(PandasDataFrameReader)
        registry.register(XarrayDatasetReader)
        # Prefer Pillow for images before the generic dataset reader.
        registry.register(ImageReader)
        registry.register(StacJobResultReader)
        return registry

    @property
    def reader_types(self) -> tuple[JobResultReaderType, ...]:
        """The tuple of registered job result readers."""
        return tuple(self._reader_types)

    def register(self, reader_type: JobResultReaderType) -> Callable[[], None]:
        """Register a job result reader.

        Args:
            reader_type: The type of the reader to be registered.

        Returns:
            A function that can be called to unregister the reader.
        """
        assert_reader_type_valid(reader_type)
        reader_id = reader_type.__dict__.get("reader_id")
        if not isinstance(reader_id, str) or not reader_id.strip():
            raise ValueError(
                "A concrete reader must explicitly declare a non-empty reader_id"
            )
        if any(
            t is not reader_type and t.reader_id == reader_id
            for t in self._reader_types
        ):
            raise ValueError(f"Duplicate job result reader ID: {reader_id!r}")

        def unregister():
            try:
                self._reader_types.remove(reader_type)
            except ValueError:
                pass

        # Remove an already registered reader type
        unregister()

        # Insert at the beginning so that readers
        # added last are used first.
        self._reader_types.insert(0, reader_type)
        return unregister

    def clear(self) -> None:
        """Clears the registry.
        Removes registered all job result readers.
        """
        self._reader_types = []
