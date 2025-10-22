#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import threading
import time
from typing import Optional

from s2gos_client.api.client import Client as ApiClient
from s2gos_client.api.exceptions import ClientError
from s2gos_client.api.transport import Transport
from s2gos_common.models import JobInfo, ProcessList

from .job_info_panel import JobInfoPanel
from .jobs_observer import JobsObserver
from .jobs_panel import JobsPanel
from .main_panel import MainPanel


class Client(ApiClient):
    def __init__(
        self,
        *,
        update_interval: float = 2.0,
        _transport: Optional[Transport] = None,
        **config,
    ):
        super().__init__(_transport=_transport, **config)
        self._jobs: dict[str, JobInfo] = {}
        self._jobs_observers: list[JobsObserver] = []
        self._update_interval = update_interval
        self._update_thread: Optional[threading.Thread] = None
        # Panels
        self._main_panel: Optional[MainPanel] = None
        self._jobs_panel: Optional[JobsPanel] = None
        self._job_info_panels: dict[str, JobInfoPanel] = {}

    def _reset_state(self):
        self._jobs = {}
        self._jobs_observers = []
        self._update_thread = None
        # Panels
        self._main_panel = None
        self._jobs_panel = None
        self._job_info_panels = {}

    def show(self) -> MainPanel:
        if self._main_panel is None:
            self._main_panel = MainPanel(
                *self._get_processes(),
                on_get_process=self.get_process,
                on_execute_process=self.execute_process,
            )
            # noinspection PyTypeChecker
            self._jobs_observers.append(self._main_panel)

        self._ensure_update_thread_is_running()

        return self._main_panel

    def show_jobs(self) -> JobsPanel:
        if self._jobs_panel is None:
            self._jobs_panel = JobsPanel(
                on_cancel_job=self._cancel_job,
                on_delete_job=self._delete_job,
                on_restart_job=self._restart_job,
                on_get_job_results=self.get_job_results,
            )
            # noinspection PyTypeChecker
            self._jobs_observers.append(self._jobs_panel)

        self._ensure_update_thread_is_running()

        return self._jobs_panel

    def show_job(self, job_id: str) -> JobInfoPanel:
        job_info_panel = self._job_info_panels.get(job_id)
        if job_info_panel is None:
            job_info_panel = JobInfoPanel()
            job_info_panel.job_info = self._jobs.get(job_id)
            self._job_info_panels[job_id] = job_info_panel
            # noinspection PyTypeChecker
            self._jobs_observers.append(job_info_panel)

        self._ensure_update_thread_is_running()

        return job_info_panel

    def close(self):
        self._reset_state()
        super().close()

    def _cancel_job(self, job_id: str):
        return self.dismiss_job(job_id)

    def _delete_job(self, job_id: str):
        return self.dismiss_job(job_id)

    # noinspection PyMethodMayBeStatic
    def _restart_job(self, _job_id: str):
        # TODO: implement job restart
        print("Not implemented.")

    def __delete__(self, instance):
        self._reset_state()

    def _ensure_update_thread_is_running(self):
        if self._update_thread is None or not self._update_thread.is_alive():
            self._update_thread = threading.Thread(
                target=self._run_jobs_updater, daemon=True
            )
            self._update_thread.start()

    def _run_jobs_updater(self):
        while self._update_thread is not None:
            if self._jobs_observers:
                self._update_jobs()
            time.sleep(self._update_interval)

    def _update_jobs(self):
        try:
            job_list = self.get_jobs()
        except ClientError as e:
            for jobs_observer in self._jobs_observers:
                jobs_observer.on_job_list_error(e)
            return

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
            for jobs_observer in self._jobs_observers:
                for job in added_jobs:
                    jobs_observer.on_job_added(job)
                for job in changed_jobs:
                    jobs_observer.on_job_changed(job)
                for job in removed_jobs:
                    jobs_observer.on_job_removed(job)
                jobs_observer.on_job_list_changed(job_list)
            self._jobs = new_jobs

    def _get_processes(self) -> tuple[ProcessList, ClientError | None]:
        try:
            return self.get_processes(), None
        except ClientError as e:
            return ProcessList(processes=[], links=[]), e
