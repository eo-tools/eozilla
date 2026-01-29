#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable, Optional, TypeAlias

import pandas as pd
import param
from pydantic import BaseModel

from cuiman.api.exceptions import ClientError
from cuiman.gui.jobs_observer import JobsObserver
from gavicore.models import JobInfo, JobList, JobResults, JobStatus

JobAction: TypeAlias = Callable[[str], Any]


@JobsObserver.register  # virtual subclass, no runtime checks
class JobsPanelViewModel(param.Parameterized):
    """
    Reactive state and logic holder for JobsPanelView.

    It implements the JobsObserver interface by protocol.
    """

    # ---- reactive state ----
    jobs = param.List(default=[])
    selection = param.List(default=[])
    message = param.String(default="")
    error = param.Parameter(default=None)
    # ---- reactive enablement ----
    cancel_disabled = param.Boolean(default=False)
    delete_disabled = param.Boolean(default=False)
    restart_disabled = param.Boolean(default=False)
    get_results_disabled = param.Boolean(default=False)

    def __init__(
        self,
        job_list: JobList,
        delete_job: Optional[JobAction] = None,
        cancel_job: Optional[JobAction] = None,
        restart_job: Optional[JobAction] = None,
        get_job_results: Optional[JobAction] = None,
    ):
        super().__init__()
        # ---- capabilities (not reactive) ----
        self._delete_job = delete_job
        self._cancel_job = cancel_job
        self._restart_job = restart_job
        self._get_job_results = get_job_results
        # ---- reactive state ----
        self.jobs = list(job_list.jobs)

    # ---- JobsObserver interface implementation ----

    def on_job_added(self, _job_info: JobInfo):
        pass

    def on_job_removed(self, _job_info: JobInfo):
        pass

    def on_job_changed(self, _job_info: JobInfo):
        pass

    def on_job_list_changed(self, job_list: JobList):
        self.jobs = list(job_list.jobs)

    def on_job_list_error(self, error: ClientError | None):
        self.error = error

    # ---- selection state ----

    def set_selection(self, selection: list[int]):
        self.selection = [self.jobs[selected_idx].jobID for selected_idx in selection]

    # ---- derived (pure) ----

    @param.depends("jobs")
    def dataframe(self) -> pd.DataFrame:
        return _jobs_to_dataframe(self.jobs)

    def selected_jobs(self) -> list[JobInfo]:
        if not self.selection:
            return []
        ids = set(self.selection)
        return [job for job in self.jobs if job.jobID in ids]

    @param.depends("jobs", "selection", watch=True)
    def _update_capabilities(self):
        self.cancel_disabled = not self._can_perform_action(
            self._cancel_job, {JobStatus.accepted, JobStatus.running}
        )
        self.delete_disabled = not self._can_perform_action(
            self._delete_job,
            {JobStatus.successful, JobStatus.dismissed, JobStatus.failed},
        )
        self.restart_disabled = not self._can_perform_action(
            self._restart_job,
            {JobStatus.successful, JobStatus.dismissed, JobStatus.failed},
        )
        jobs = self.selected_jobs()
        self.get_results_disabled = not (
            self._get_job_results is not None
            and len(jobs) == 1
            and _job_requirements_fulfilled(
                jobs, {JobStatus.successful, JobStatus.failed}
            )
        )

    def _can_perform_action(
        self, action: JobAction | None, statuses: set[JobStatus]
    ) -> bool:
        jobs = self.selected_jobs()
        return action is not None and _job_requirements_fulfilled(jobs, statuses)

    # ---- actions mutate state ----

    def cancel_selected(self):
        self.message = self._run_action(
            self._cancel_job,
            "✅ Cancelled {job}",
            "⚠️ Failed cancelling {job}: {message}",
        )

    def delete_selected(self):
        self.message = self._run_action(
            self._delete_job,
            "✅ Deleted {job}",
            "⚠️ Failed deleting {job}: {message}",
        )

    def restart_selected(self):
        self.message = self._run_action(
            self._restart_job,
            "✅ Restarted {job}",
            "⚠️ Failed restarting {job}: {message}",
        )

    def get_results_for_selected(self, var_name="_results"):
        def set_ipython_value(_job_id: str, results: JobResults | dict):
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
            self._get_job_results,
            set_ipython_value,
            "⚠️ Failed to get results for {job}: {message}",
        )

    def _run_action(
        self,
        action: JobAction | None,
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


class JsonDict(dict):
    """A JSON object value that renders nicely in Jupyter notebooks."""

    def __init__(self, name: str, *args, **kwargs):
        # noinspection PyArgumentList
        super().__init__(*args, **kwargs)
        self._name = name

    def _repr_json_(self):
        return self, {"root": f"{self._name}:"}
