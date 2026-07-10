#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from panel.layout import Panel

from cuiman.gui.jobs_observer import JobsObserver
from cuiman.gui.panels import JobsPanelView, JobsPanelViewModel
from gavicore.models import JobInfo, JobList, JobStatus


class JobsFormTest(TestCase):
    def test_it(self):
        jobs_panel = _create_jobs_form()
        self.assertIsInstance(jobs_panel.__panel__(), Panel)

    def test_vm_is_observer(self):
        jobs_form = _create_jobs_form()
        self.assertIsInstance(jobs_form.vm, JobsObserver)


def _create_jobs_form() -> JobsPanelView:
    job_list = JobList(
        jobs=[
            JobInfo(
                jobID="job_1",
                processID="gen_scene",
                status=JobStatus.successful,
                progress=100,
            ),
            JobInfo(
                jobID="job_2",
                processID="gen_scene",
                status=JobStatus.running,
                progress=23,
            ),
            JobInfo(
                jobID="job_3",
                processID="gen_scene",
                status=JobStatus.failed,
                progress=97,
            ),
            JobInfo(
                jobID="job_4",
                processID="gen_scene",
                status=JobStatus.accepted,
            ),
        ],
        links=[],
    )

    def on_delete_job(_job_id: str):
        pass

    def on_cancel_job(_job_id: str):
        pass

    def on_restart_job(_job_id: str):
        pass

    def on_get_job_results(_job_id: str):
        pass

    panel = JobsPanelView(
        JobsPanelViewModel(
            job_list,
            delete_job=on_delete_job,
            cancel_job=on_cancel_job,
            restart_job=on_restart_job,
            get_job_results=on_get_job_results,
        )
    )
    return panel
