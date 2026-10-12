#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from gavicore.models.core import JobResults

from .async_client import AsyncClient
from .client import Client
from .config import ClientConfig
from .exceptions import ClientError
from .jobs import JobMonitor, JobOptions

__all__ = [
    "AsyncClient",
    "Client",
    "ClientConfig",
    "ClientError",
    "JobMonitor",
    "JobOptions",
]


def _repr_job_results_as_html(self: JobResults) -> str:
    """Render job outputs in notebooks without fetching or displaying data."""
    from .assets.job_results import _job_results_html

    return _job_results_html(self)


# Install Cuiman's presentation without introducing a gavicore dependency on it.
JobResults._repr_html_ = _repr_job_results_as_html  # type: ignore[attr-defined]
