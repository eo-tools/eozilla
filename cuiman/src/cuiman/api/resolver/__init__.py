#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Developer contracts for resource discovery and resolver-owned transformations."""

from .context import (
    DiscoveryError,
    DiscoveryLimits,
    MetadataDocument,
    MetadataFetcher,
    MetadataLoader,
    MetadataResponse,
    ResolutionContext,
)
from .registry import JobResultResolverRegistry
from .resolver import JobResultResolver, resolve_job_result
from .transformer import (
    ComposedJobResultResolver,
    FolderResourceTransformer,
    ResourceEntry,
    ResourceTransformer,
)

__all__ = [
    "ComposedJobResultResolver",
    "DiscoveryError",
    "DiscoveryLimits",
    "FolderResourceTransformer",
    "JobResultResolver",
    "JobResultResolverRegistry",
    "MetadataDocument",
    "MetadataFetcher",
    "MetadataLoader",
    "MetadataResponse",
    "ResolutionContext",
    "ResourceEntry",
    "ResourceTransformer",
    "resolve_job_result",
]
