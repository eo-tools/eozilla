#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from gavicore.models.core import JobInfo


class JobResultReadError(Exception):
    """A reader could not read the selected job result or asset."""


class JobResultStatusError(JobResultReadError):
    """A job result cannot be read because the job did not succeed."""

    def __init__(self, job_info: JobInfo):
        message = (
            f"Cannot read results of job #{job_info.jobID} "
            f"because the job status is '{job_info.status.value}'"
        )
        if job_info.message:
            message += f": {job_info.message}"
        super().__init__(message)
        self.job_info = job_info


class StacJobResultReadError(JobResultReadError):
    """Sanitized STAC parsing or metadata-access failure.

    Required STAC failures stop dispatch instead of returning an unrelated
    representation. Weak JSON/GeoJSON candidates may allow another reader.
    """

    def __init__(self, message: str, *, required: bool = True):
        super().__init__(message)
        self.required = required
        """Whether this failure forbids fallback to unrelated readers."""
