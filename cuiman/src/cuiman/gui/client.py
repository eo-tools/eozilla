#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import threading
import time
from typing import Any, Optional

from cuiman.api.client import Client as ApiClient
from cuiman.api.config import ClientConfig
from cuiman.api.exceptions import ClientError
from cuiman.api.transport import Transport
from gavicore.models import ProcessList

from .job_info_panel import JobInfoPanel
from .jobs_event_bus import JobsEventBus
from .jobs_panel import JobsPanel
from .main_panel import MainPanel


class Client(ApiClient):
    def __init__(
        self,
        *,
        update_interval: float = 2.0,
        _transport: Optional[Transport] = None,
        **config: Any,
    ):
        super().__init__(_transport=_transport, **config)
        # self._jobs: dict[str, JobInfo] = {}
        self._jobs_event_bus = JobsEventBus()
        self._update_interval = update_interval
        self._update_thread: Optional[threading.Thread] = None

    def _reset_state(self):
        self._update_thread = None

    def show(self, **kwargs: Any) -> MainPanel:
        """Shows the client's main GUI.

        Args:
            kwargs: Extra GUI configuration parameters.
                The default client does not have any extra configuration parameters.
                However, applications using `cuiman.gui.Client` may make special
                use of them. Refer to a dedicated documentation in this case.

        Returns:
            MainPanel: The main GUI panel object.
        """
        from functools import partial

        config_cls: type[ClientConfig] = type(self.config)
        accept_process = (
            partial(config_cls.accept_process, **kwargs)
            if kwargs
            else config_cls.accept_process
        )
        level = kwargs.get("level")
        show_advanced = level == "advanced" if level is not None else None
        main_panel = MainPanel(
            *self._get_processes(),
            on_get_process=self.get_process,
            on_execute_process=self.execute_process,
            accept_process=accept_process,
            accept_input=config_cls.accept_input,
            show_advanced=show_advanced,
        )
        # noinspection PyTypeChecker
        self._jobs_event_bus.register(main_panel)
        self._ensure_update_thread_is_running()
        return main_panel

    def show_jobs(self) -> JobsPanel:
        jobs_panel = JobsPanel(
            on_cancel_job=self._cancel_job,
            on_delete_job=self._delete_job,
            on_restart_job=self._restart_job,
            on_get_job_results=self.get_job_results,
        )
        jobs_panel.on_job_list_changed(self._jobs_event_bus.job_list)
        # noinspection PyTypeChecker
        self._jobs_event_bus.register(jobs_panel)
        self._ensure_update_thread_is_running()
        return jobs_panel

    def show_job(self, job_id: str) -> JobInfoPanel:
        job_info = self._jobs_event_bus.get_job(job_id)
        if job_info is None:
            job_info = self.get_job(job_id)
        job_info_panel = JobInfoPanel()
        job_info_panel.job_info = job_info
        # noinspection PyTypeChecker
        self._jobs_event_bus.register(job_info_panel)
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
            print("Update thread is now running")

    def _run_jobs_updater(self):
        while self._update_thread is not None:
            self._jobs_event_bus.poll(self)
            time.sleep(self._update_interval)

    def _get_processes(self) -> tuple[ProcessList, ClientError | None]:
        try:
            return self.get_processes(), None
        except ClientError as e:
            return ProcessList(processes=[], links=[]), e
