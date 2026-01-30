#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from panel.layout import Panel

from cuiman.gui.jobs_observer import JobsObserver
from cuiman.gui.panels import MainPanelView
from gavicore.models import (
    InputDescription,
    JobInfo,
    JobStatus,
    JobType,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
    ProcessSummary,
    Schema,
)

bbox_input = InputDescription(
    title="Bounding box",
    schema=Schema.model_validate(
        {
            "type": "array",
            "items": {"type": "number"},
            "format": "bbox",
        }
    ),
)

date_input = InputDescription(
    title="Date",
    schema=Schema.model_validate(
        {
            "type": "string",
            "format": "date",
            "default": "2025-01-01",
        }
    ),
)

int_input = InputDescription(
    title="Periodicity",
    schema=Schema.model_validate(
        {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
        },
    ),
)


class MainFormTest(TestCase):
    def test_is_observer(self):
        main_panel = _create_main_panel({})
        self.assertIsInstance(main_panel, JobsObserver)

    def test_with_int_input(self):
        main_panel = _create_main_panel({"periodicity": int_input})
        self.assertIsInstance(main_panel.__panel__(), Panel)

    def test_with_bbox_input(self):
        main_panel = _create_main_panel({"bbox": bbox_input})
        self.assertIsInstance(main_panel.__panel__(), Panel)

    def test_with_date_input(self):
        main_panel = _create_main_panel({"date": date_input})
        self.assertIsInstance(main_panel.__panel__(), Panel)


def _create_main_panel(process_inputs: dict[str, InputDescription]) -> MainPanelView:
    process = ProcessDescription(
        id="gen_scene",
        title="Generate a scene",
        version="1",
        inputs=process_inputs,
    )

    def on_get_process(_process_id: str):
        return process

    def on_execute_process(process_id: str, _request: ProcessRequest):
        return JobInfo(
            processID=process_id,
            jobID="job_8",
            type=JobType.process,
            status=JobStatus.successful,
        )

    process_list = ProcessList(processes=[process], links=[])

    return MainPanelView(
        process_list,
        None,
        on_get_process,
        on_execute_process,
        accept_process,
        is_advanced_input,
    )


# noinspection PyUnusedLocal
def accept_process(p: ProcessSummary) -> bool:
    return True


# noinspection PyUnusedLocal
def is_advanced_input(p: ProcessDescription, i_name: str, i: InputDescription) -> bool:
    return False
