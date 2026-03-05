#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from gavicore.models import JobInfo


class JobResultOpenError(Exception):
    """A job result could not be opened.

    This error is potentially raised by the
    [OpenerRegistry.open_result()][OpenerRegistry.open_result]
    method.
    """


class JobResultStatusError(JobResultOpenError):
    """A job result could not be opened.

    This error is potentially raised by the
    [OpenerRegistry.open_result()][OpenerRegistry.open_result]
    method.
    """

    def __init__(self, job_info: JobInfo):
        message = (
            f"Cannot open results of job #{job_info.jobID} "
            f"because the job status is '{job_info.status.value}'"
        )
        if job_info.message:
            message += f": {job_info.message}"
        super().__init__(message)
        self.job_info = job_info
