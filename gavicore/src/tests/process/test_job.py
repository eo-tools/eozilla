#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pydantic
import pytest

from s2gos_common.models import JobResults, JobStatus, ProcessRequest, Subscriber
from s2gos_common.process import Process
from s2gos_common.process.job import (
    Job,
    JobCancelledException,
    JobContext,
    NullJobContext,
)

from .test_process import f1


def fn_success(x: int, y: int) -> int:
    return x * y


def fn_success_with_defaults(x: int = 0, y: int = 0) -> int:
    return x + y


def fn_success_body_ctx(path: str) -> str:
    ctx = JobContext.get()
    ctx.check_cancelled()
    ctx.report_progress(progress=0)
    ctx.report_progress(progress=50, message="Almost done")
    ctx.report_progress(progress=100)
    return path + "/result1.zarr"


def fn_success_arg_ctx(ctx: JobContext, path: str) -> str:
    ctx.check_cancelled()
    ctx.report_progress(progress=0)
    ctx.report_progress(progress=50, message="Almost done")
    ctx.report_progress(progress=100)
    return path + "/result2.zarr"


class Params(pydantic.BaseModel):
    p1: bool
    p2: float
    p3: str


def fn_success_inputs_arg(ctx: JobContext, params: Params) -> str:
    ctx.report_progress(message="Done!")
    return f"{params.p1!r}-{params.p2!r}-{params.p3!r}"


# noinspection PyUnusedLocal
def fn_cancel_exc(path: str) -> str:
    raise JobCancelledException


# noinspection PyUnusedLocal
def fn_exc(path: str) -> str:
    raise OSError("File not found")


class JobTest(TestCase):
    def test_ctor(self):
        job = Job.create(
            process=Process.create(fn_success, id="fn_success"),
            job_id="job_27",
            request=ProcessRequest(inputs={"x": True, "y": 2}),
        )
        self.assertEqual("fn_success", job.job_info.processID)
        self.assertEqual("job_27", job.job_info.jobID)
        self.assertEqual(None, job.job_info.progress)
        self.assertEqual({"x": True, "y": 2}, job.function_kwargs)

    def test_context(self):
        job = Job.create(
            process=Process.create(fn_success, id="fn_success"),
            job_id="job_27",
            request=ProcessRequest(inputs={"x": False, "y": 2}),
        )
        self.assertEqual(False, job.is_cancelled())
        self.assertEqual(None, job.check_cancelled())
        job.report_progress(progress=35, message="2/6 input files downloaded")
        self.assertEqual(35, job.job_info.progress)
        self.assertEqual("2/6 input files downloaded", job.job_info.message)
        job.report_progress(message="3/6 input files downloaded")
        self.assertEqual(35, job.job_info.progress)
        self.assertEqual("3/6 input files downloaded", job.job_info.message)
        job.report_progress(progress=40)
        self.assertEqual(40, job.job_info.progress)
        self.assertEqual("3/6 input files downloaded", job.job_info.message)

        job.cancel()
        self.assertEqual(True, job.is_cancelled())
        with pytest.raises(JobCancelledException):
            job.check_cancelled()
        self.assertEqual(40, job.job_info.progress)
        self.assertEqual("3/6 input files downloaded", job.job_info.message)

    def test_run_success(self):
        job = Job.create(
            process=Process.create(fn_success, id="fn_success"),
            job_id="job_41",
            request=ProcessRequest(inputs={"x": 3, "y": 9}),
        )
        job_results = job.run()
        # noinspection PyArgumentList
        self.assertEqual(JobResults({"return_value": 27}), job_results)
        self.assertEqual(JobStatus.successful, job.job_info.status)
        self.assertEqual(None, job.job_info.progress)
        self.assertEqual(None, job.job_info.message)

    def test_run_success_with_defaults(self):
        job = Job.create(
            process=Process.create(
                fn_success_with_defaults, id="fn_success_with_defaults"
            ),
            job_id="job_652",
            request=ProcessRequest(inputs={"y": 13}),
        )
        job_results = job.run()
        # noinspection PyArgumentList
        self.assertEqual(JobResults({"return_value": 13}), job_results)
        self.assertEqual(JobStatus.successful, job.job_info.status)
        self.assertEqual(None, job.job_info.progress)
        self.assertEqual(None, job.job_info.message)

    def test_run_success_body_ctx_report(self):
        job = Job.create(
            process=Process.create(fn_success_body_ctx, id="fn_success_body_ctx"),
            job_id="job_41",
            request=ProcessRequest(inputs={"path": "outputs"}),
        )
        job_results = job.run()
        # noinspection PyArgumentList
        self.assertEqual(
            JobResults({"return_value": "outputs/result1.zarr"}), job_results
        )
        self.assertEqual(JobStatus.successful, job.job_info.status)
        self.assertEqual(100, job.job_info.progress)
        self.assertEqual("Almost done", job.job_info.message)

    def test_run_success_arg_ctx_report(self):
        job = Job.create(
            process=Process.create(fn_success_arg_ctx, id="fn_success_arg_ctx"),
            job_id="job_42",
            request=ProcessRequest(inputs={"path": "outputs"}),
        )
        job_results = job.run()
        # noinspection PyArgumentList
        self.assertEqual(
            JobResults({"return_value": "outputs/result2.zarr"}), job_results
        )
        self.assertEqual(JobStatus.successful, job.job_info.status)
        self.assertEqual(100, job.job_info.progress)
        self.assertEqual("Almost done", job.job_info.message)

    def test_run_success_input_args(self):
        job = Job.create(
            process=Process.create(
                fn_success_inputs_arg, id="fn_success_inputs_arg", inputs_arg=True
            ),
            job_id="job_42",
            request=ProcessRequest(inputs={"p1": True, "p2": 0.5, "p3": "abc"}),
        )
        job_results = job.run()
        # noinspection PyArgumentList
        self.assertEqual(JobResults({"return_value": "True-0.5-'abc'"}), job_results)
        self.assertEqual(JobStatus.successful, job.job_info.status)
        self.assertEqual(None, job.job_info.progress)
        self.assertEqual("Done!", job.job_info.message)

    def test_run_exc(self):
        job = Job.create(
            process=Process.create(fn_exc, id="fn_exc"),
            job_id="job_41",
            request=ProcessRequest(inputs={"path": "outputs"}),
        )
        result = job.run()
        self.assertEqual(None, result)
        self.assertEqual(JobStatus.failed, job.job_info.status)

    def test_run_failed(self):
        job = Job.create(
            process=Process.create(fn_cancel_exc, id="fn_cancel_exc"),
            job_id="job_41",
            request=ProcessRequest(inputs={"path": "outputs"}),
        )
        result = job.run()
        self.assertEqual(None, result)
        self.assertEqual(JobStatus.dismissed, job.job_info.status)

    def test_run_success_report_with_subscriber(self):
        job = Job.create(
            process=Process.create(fn_success_body_ctx, id="fn_success_report"),
            job_id="job_3092",
            request=ProcessRequest(
                inputs={"path": "outputs"},
                subscriber=Subscriber(
                    **{
                        "successUri": "http://localhost:7000/cb/success",
                        "inProgressUri": "http://localhost:7000/cb/progress",
                        "failedUri": "http://localhost:7000/cb/failed",
                    }
                ),
            ),
        )
        result = job.run()
        self.assertIsInstance(result, JobResults)
        self.assertEqual(JobStatus.successful, job.job_info.status)

    def test_run_exc_with_subscriber(self):
        job = Job.create(
            process=Process.create(fn_exc, id="fn_exc"),
            job_id="job_3092",
            request=ProcessRequest(
                inputs={"path": "outputs"},
                subscriber=Subscriber(
                    **{
                        "successUri": "http://localhost:7000/cb/success",
                        "inProgressUri": "http://localhost:7000/cb/progress",
                        "failedUri": "http://localhost:7000/cb/failed",
                    }
                ),
            ),
        )
        result = job.run()
        self.assertEqual(None, result)
        self.assertEqual(JobStatus.failed, job.job_info.status)


class GetJobContextTest(TestCase):
    def test_null(self):
        job_context = JobContext.get()
        self.assertIsInstance(job_context, NullJobContext)

    def test_valid(self):
        __job_context__ = Job(  # noqa: F841
            process=Process.create(f1),
            job_id="b",
            function_kwargs={"x": 4},
        )
        value = JobContext.get()
        self.assertIs(__job_context__, value)


class NullJobContextTest(TestCase):
    def test_it(self):
        job_context = NullJobContext()
        self.assertFalse(job_context.report_progress(progress=85))
        self.assertFalse(job_context.is_cancelled())
        self.assertFalse(job_context.check_cancelled())
