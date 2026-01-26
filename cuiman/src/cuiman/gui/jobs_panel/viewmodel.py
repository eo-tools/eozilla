#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable, Any
from gavicore.models import JobList, JobStatus
from cuiman.api.exceptions import ClientError
from .state import JobsPanelState

JobAction = Callable[[str], Any]


class JobsPanelViewModel:
    def __init__(
        self,
        state: JobsPanelState,
        on_delete: JobAction | None = None,
        on_cancel: JobAction | None = None,
        on_restart: JobAction | None = None,
        on_get_results: JobAction | None = None,
    ):
        self.state = state
        self.on_delete = on_delete
        self.on_cancel = on_cancel
        self.on_restart = on_restart
        self.on_get_results = on_get_results

    # ---- state updates (observer side) ----

    def on_job_list_changed(self, job_list: JobList):
        self.state.jobs = list(job_list.jobs)

    def on_job_list_error(self, error):
        self.state.error = error

    def update_selection(self, indices: list[int]):
        self.state.selected_indices = indices

    # ---- derived UI state ----

    def can_cancel(self) -> bool:
        return self._check({JobStatus.accepted, JobStatus.running}, self.on_cancel)

    def can_delete(self) -> bool:
        return self._check(
            {JobStatus.successful, JobStatus.dismissed, JobStatus.failed},
            self.on_delete,
        )

    def can_restart(self) -> bool:
        return self._check(
            {JobStatus.successful, JobStatus.dismissed, JobStatus.failed},
            self.on_restart,
        )

    def can_get_results(self) -> bool:
        jobs = self.state.selected_jobs()
        return (
            self.on_get_results is not None
            and len(jobs) == 1
            and jobs[0].status in {JobStatus.successful, JobStatus.failed}
        )

    def _check(self, statuses, action):
        jobs = self.state.selected_jobs()
        return bool(action and jobs and all(j.status in statuses for j in jobs))

    # ---- actions ----

    def run_action(
        self, action: JobAction, success_cb: Callable[[str, Any], None], error_fmt: str
    ):
        messages = []
        for job in self.state.selected_jobs():
            try:
                result = action(job.jobID)
                messages.append(success_cb(job.jobID, result))
            except ClientError as e:
                messages.append(
                    error_fmt.format(job=job.jobID, message=e.api_error.detail)
                )
        return messages
