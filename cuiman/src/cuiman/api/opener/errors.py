#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from gavicore.models import JobInfo


class JobResultOpenError(Exception):
    """No configured opener could successfully open the selected resource."""


class JobResultStatusError(JobResultOpenError):
    """Job-output opening stopped because the job failed or was canceled."""

    def __init__(self, job_info: JobInfo):
        message = (
            f"Cannot open results of job #{job_info.jobID} "
            f"because the job status is '{job_info.status.value}'"
        )
        if job_info.message:
            message += f": {job_info.message}"
        super().__init__(message)
        self.job_info = job_info
