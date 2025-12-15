#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import warnings
from typing import Any, Callable
from weakref import WeakSet

from cuiman.api import Client, ClientError
from gavicore.models import JobInfo, JobList

from .jobs_observer import JobsObserver


class JobsEventBus:
    def __init__(self):
        self._jobs: dict[str, JobInfo] = {}
        self._jobs_observers: WeakSet[JobsObserver] = WeakSet()

    def get_job(self, job_id: str) -> JobInfo | None:
        return self._jobs.get(job_id)

    def register(self, jobs_observer: JobsObserver):
        self._jobs_observers.add(jobs_observer)

    def poll(self, client: Client):
        try:
            job_list = client.get_jobs()
            self._dispatch(job_list)
        except ClientError as error:
            self._emit("job_list_error", error)

    def _dispatch(self, job_list: JobList):
        old_jobs = self._jobs
        new_jobs = {job.jobID: job for job in job_list.jobs}

        added_jobs = [job for job_id, job in new_jobs.items() if job_id not in old_jobs]
        changed_jobs = [
            job
            for job_id, job in new_jobs.items()
            if job_id in old_jobs and job != old_jobs[job_id]
        ]
        removed_jobs = [
            job for job_id, job in old_jobs.items() if job_id not in new_jobs
        ]

        if added_jobs or changed_jobs or removed_jobs:
            for job in added_jobs:
                self._emit("job_added", job)
            for job in changed_jobs:
                self._emit("job_changed", job)
            for job in removed_jobs:
                self._emit("job_removed", job)
            self._emit("job_list_changed", job_list)
            self._jobs = new_jobs

    def _emit(self, event_type: str, event_arg: Any):
        for jobs_observer in self._jobs_observers:
            try:
                method: Callable[[Any], None] = getattr(
                    jobs_observer, f"on_{event_type}"
                )
                method(event_arg)
            except ReferenceError:
                # Handle case where reference is already gone, this is ok.
                # Hard to reach by unit tests.
                pass  # pragma: no cover
            except BaseException as e:
                warnings.warn(f"Error emitting event of type {event_type!r}: {e}")
