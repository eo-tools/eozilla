#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable, Optional, TypeAlias

from pydantic import BaseModel
import param
import pandas as pd

from cuiman.api.exceptions import ClientError
from gavicore.models import JobInfo, JobList, JobResults, JobStatus

from ..util import JsonDict

JobAction: TypeAlias = Callable[[str], Any]


class JobsPanelViewModel(param.Parameterized):
    # ---- reactive state ----
    jobs = param.List(default=[])
    selection = param.List(default=[])
    message = param.String(default="")
    error = param.Parameter(default=None)

    # ---- capabilities (not reactive) ----
    on_delete_job: Optional[JobAction] = None
    on_cancel_job: Optional[JobAction] = None
    on_restart_job: Optional[JobAction] = None
    on_get_job_results: Optional[JobAction] = None

    def __init__(self, job_list: JobList, **kwargs):
        super().__init__()
        self.jobs = list(job_list.jobs)
        for k, v in kwargs.items():
            setattr(self, k, v)

    # ---- observer inputs ----

    def on_job_list_changed(self, job_list: JobList):
        self.jobs = list(job_list.jobs)

    def on_job_list_error(self, error: ClientError | None):
        self.error = error

    def set_selection(self, selection: list[int]):
        self.selection = list(selection or [])

    # ---- derived (pure) ----

    @param.depends("jobs", "selection")
    def dataframe(self) -> pd.DataFrame:
        return _jobs_to_dataframe(self.jobs)

    def selected_jobs(self) -> list[JobInfo]:
        if not self.selection:
            return []
        ids = {self.jobs[i].jobID for i in self.selection}
        return [j for j in self.jobs if j.jobID in ids]

    @param.depends("jobs", "selection")
    def can_cancel(self) -> bool:
        return self._can(self.on_cancel_job, {JobStatus.accepted, JobStatus.running})

    @param.depends("jobs", "selection")
    def can_delete(self) -> bool:
        return self._can(
            self.on_delete_job,
            {JobStatus.successful, JobStatus.dismissed, JobStatus.failed},
        )

    @param.depends("jobs", "selection")
    def can_restart(self) -> bool:
        return self._can(
            self.on_restart_job,
            {JobStatus.successful, JobStatus.dismissed, JobStatus.failed},
        )

    @param.depends("jobs", "selection")
    def can_get_results(self) -> bool:
        jobs = self.selected_jobs()
        return (
            self.on_get_job_results is not None
            and len(jobs) == 1
            and _job_requirements_fulfilled(
                jobs, {JobStatus.successful, JobStatus.failed}
            )
        )

    def _can(self, action: JobAction, statuses: set[JobStatus]):
        jobs = self.selected_jobs()
        return action is not None and _job_requirements_fulfilled(jobs, statuses)

    # ---- actions mutate state ----

    def cancel_selected(self):
        self.message = self._run_action(
            self.on_cancel_job,
            "✅ Cancelled {job}",
            "⚠️ Failed cancelling {job}: {message}",
        )

    def delete_selected(self):
        self.message = self._run_action(
            self.on_delete_job,
            "✅ Deleted {job}",
            "⚠️ Failed deleting {job}: {message}",
        )

    def restart_selected(self):
        self.message = self._run_action(
            self.on_restart_job,
            "✅ Restarted {job}",
            "⚠️ Failed restarting {job}: {message}",
        )

    def get_results_for_selected(self, var_name="_results"):
        def handle(_job_id: str, results: JobResults | dict):
            # noinspection PyProtectedMember
            from IPython import get_ipython

            value = results.root if isinstance(results, JobResults) else results
            if isinstance(value, dict):
                value = JsonDict(
                    "Results",
                    {
                        k: (v.model_dump() if isinstance(v, BaseModel) else v)
                        for k, v in value.items()
                    },
                )

            ip = get_ipython()
            if ip is None:
                raise RuntimeError("Not running inside IPython")
            ip.user_ns[var_name] = value
            return f"✅ Stored results of {{job}} in **`{var_name}`**"

        self.message = self._run_action(
            self.on_get_job_results,
            handle,
            "⚠️ Failed to get results for {job}: {message}",
        )

    def _run_action(
        self,
        action: JobAction,
        success_fmt: str | Callable[[str, Any], str],
        error_fmt: str,
    ) -> str:
        if action is None:
            return ""

        messages = []
        for job in self.selected_jobs():
            job_text = f"job `{job.jobID}`"
            try:
                result = action(job.jobID)
                if callable(success_fmt):
                    messages.append(success_fmt(job.jobID, result).format(job=job_text))
                else:
                    messages.append(success_fmt.format(job=job_text))
            except Exception as e:
                msg = (
                    f"{e}: {e.api_error.detail}"
                    if isinstance(e, ClientError)
                    else str(e)
                )
                messages.append(error_fmt.format(job=job_text, message=msg))

        return "  \n".join(messages)


def _jobs_to_dataframe(jobs: list[JobInfo]):
    return pd.DataFrame([_job_to_dataframe_row(job) for job in jobs])


def _job_to_dataframe_row(job: JobInfo):
    return {
        "process_id": job.processID,
        "job_id": job.jobID,
        "status": job.status.value,
        "progress": job.progress or 0,
        "message": job.message or "-",
    }


def _job_requirements_fulfilled(
    jobs: list[JobInfo], requirements: set[JobStatus]
) -> bool:
    return bool(jobs) and all(j.status in requirements for j in jobs)
