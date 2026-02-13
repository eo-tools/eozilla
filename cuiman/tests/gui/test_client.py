#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any
from unittest import TestCase

from cuiman.api.transport import Transport, TransportArgs
from cuiman.gui import Client as GuiClient
from cuiman.gui.panels import JobsPanelView, MainPanelView
from gavicore.models import JobList, ProcessList


class ClientTest(TestCase):
    def test_show(self):
        class _MockTransport(Transport):
            def call(self, args: TransportArgs) -> Any:
                match (args.method, args.path):
                    case ("get", "/processes"):
                        return ProcessList(processes=[], links=[])
                    case ("get", "/jobs"):
                        return JobList(jobs=[], links=[])
                    case _:
                        raise Exception("Unhandled case in mock")

            def close(self):
                pass

        client = GuiClient(api_url="https://api.ok.ko", _transport=_MockTransport())
        processes_form = client.show()
        self.assertIsInstance(processes_form, MainPanelView)
        client.close()

    def test_show_jobs(self):
        class _MockTransport(Transport):
            def call(self, args: TransportArgs) -> Any:
                if (args.method, args.path) == ("get", "/jobs"):
                    return JobList(jobs=[], links=[])
                return None

            def close(self):
                pass

        client = GuiClient(api_url="https://api.ok.ko", _transport=_MockTransport())
        jobs_form = client.show_jobs()
        self.assertIsInstance(jobs_form, JobsPanelView)
