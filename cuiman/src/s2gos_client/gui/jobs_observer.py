#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod

from s2gos_client import ClientError
from s2gos_common.models import JobInfo, JobList


class JobsObserver(ABC):
    """Observes job and job list changes."""

    @abstractmethod
    def on_job_added(self, job_info: JobInfo):
        """Called after a job has been added."""

    @abstractmethod
    def on_job_changed(self, job_info: JobInfo):
        """Called after a job has been changed."""

    @abstractmethod
    def on_job_removed(self, job_info: JobInfo):
        """Called after a job has been removed."""

    @abstractmethod
    def on_job_list_changed(self, job_list: JobList):
        """Called after the current list of jobs changed."""

    @abstractmethod
    def on_job_list_error(self, error: ClientError | None):
        """Called if an error occurred while getting current list of jobs."""
