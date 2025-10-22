#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any
from unittest import TestCase

from s2gos_client.api.transport import Transport, TransportArgs
from s2gos_client.gui import Client as GuiClient
from s2gos_client.gui.jobs_panel import JobsPanel
from s2gos_client.gui.main_panel import MainPanel
from s2gos_common.models import JobList, ProcessList


class ClientTest(TestCase):
    def test_show_processes(self):
        class _MockTransport(Transport):
            def call(self, args: TransportArgs) -> Any:
                if (args.method, args.path) == ("get", "/processes"):
                    return ProcessList(processes=[], links=[])
                return None

        client = GuiClient(_transport=_MockTransport())
        processes_form = client.show()
        self.assertIsInstance(processes_form, MainPanel)

    def test_show_jobs(self):
        class _MockTransport(Transport):
            def call(self, args: TransportArgs) -> Any:
                if (args.method, args.path) == ("get", "/jobs"):
                    return JobList(jobs=[], links=[])
                return None

        client = GuiClient(_transport=_MockTransport())
        jobs_form = client.show_jobs()
        self.assertIsInstance(jobs_form, JobsPanel)
