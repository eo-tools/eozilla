#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from panel.layout import Panel

from s2gos_client.gui.jobs_observer import JobsObserver
from s2gos_client.gui.jobs_panel import JobsPanel
from s2gos_common.models import JobInfo, JobList, JobStatus, JobType


class JobsFormTest(TestCase):
    def test_it(self):
        jobs_panel = _create_jobs_form()
        self.assertIsInstance(jobs_panel.__panel__(), Panel)

    def test_is_observer(self):
        jobs_form = _create_jobs_form()
        self.assertIsInstance(jobs_form, JobsObserver)


def _create_jobs_form() -> JobsPanel:
    job_list = JobList(
        jobs=[
            JobInfo(
                type=JobType.process,
                processID="gen_scene",
                jobID="job_1",
                status=JobStatus.successful,
                progress=100,
            ),
            JobInfo(
                type=JobType.process,
                processID="gen_scene",
                jobID="job_2",
                status=JobStatus.running,
                progress=23,
            ),
            JobInfo(
                type=JobType.process,
                processID="gen_scene",
                jobID="job_3",
                status=JobStatus.failed,
                progress=97,
            ),
            JobInfo(
                type=JobType.process,
                processID="gen_scene",
                jobID="job_4",
                status=JobStatus.accepted,
            ),
        ],
        links=[],
    )

    def on_delete_job(job_id: str):
        pass

    def on_cancel_job(job_id: str):
        pass

    def on_restart_job(job_id: str):
        pass

    def on_get_job_results(job_id: str):
        pass

    panel = JobsPanel(
        on_delete_job=on_delete_job,
        on_cancel_job=on_cancel_job,
        on_restart_job=on_restart_job,
        on_get_job_results=on_get_job_results,
    )
    panel.on_job_list_changed(job_list)
    return panel
