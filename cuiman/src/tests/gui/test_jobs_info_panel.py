#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from panel.layout import Panel

from s2gos_client.gui.job_info_panel import JobInfoPanel
from s2gos_client.gui.jobs_observer import JobsObserver


class JobInfoPanelTest(TestCase):
    def test_with_date_input(self):
        job_info_panel = JobInfoPanel()
        self.assertIsInstance(job_info_panel.__panel__(), Panel)

    def test_is_observer(self):
        job_info_panel = JobInfoPanel()
        self.assertIsInstance(job_info_panel, JobsObserver)
