#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from cuiman import ClientError
from cuiman.gui.jobs_event_bus import JobsEventBus
from cuiman.gui.jobs_observer import JobsObserver
from gavicore.models import ApiError, JobInfo, JobList, JobStatus, JobType

client_error = ClientError("Argh!", ApiError(**{"type": "server"}))


class ClientMock:
    def __init__(self, job_list: JobList | None):
        self.job_list = job_list

    def get_jobs(self) -> JobList:
        if self.job_list is None:
            raise client_error
        return self.job_list


class MyJobsObserver(JobsObserver):
    def __init__(self):
        self.records: list[tuple[str, Any]] = []

    def on_job_added(self, job_info: JobInfo):
        self.records.append(("job_added", job_info))

    def on_job_changed(self, job_info: JobInfo):
        self.records.append(("job_changed", job_info))

    def on_job_removed(self, job_info: JobInfo):
        self.records.append(("job_removed", job_info))

    def on_job_list_changed(self, job_list: JobList):
        self.records.append(("job_list_changed", job_list))

    def on_job_list_error(self, error: ClientError | None):
        self.records.append(("job_list_error", error))


def test_job_added():
    bus = JobsEventBus()

    obs = MyJobsObserver()
    bus.register(obs)

    job_1 = JobInfo(type=JobType.process, jobID="1", status=JobStatus.accepted)
    job_2 = JobInfo(type=JobType.process, jobID="2", status=JobStatus.running)
    job_list = JobList(jobs=[job_1, job_2], links=[])
    # noinspection PyTypeChecker
    bus.poll(ClientMock(job_list))

    assert obs.records == [
        ("job_added", job_1),
        ("job_added", job_2),
        ("job_list_changed", job_list),
    ]
    assert bus.get_job("1") == job_1
    assert bus.get_job("2") == job_2
    assert bus.job_list == job_list


def test_job_changed():
    bus = JobsEventBus()

    obs = MyJobsObserver()
    bus.register(obs)

    job_1 = JobInfo(type=JobType.process, jobID="1", status=JobStatus.accepted)
    job_2a = JobInfo(type=JobType.process, jobID="2", status=JobStatus.running)
    job_list_1 = JobList(jobs=[job_1, job_2a], links=[])
    # noinspection PyTypeChecker
    bus.poll(ClientMock(job_list_1))

    job_2b = JobInfo(type=JobType.process, jobID="2", status=JobStatus.successful)
    job_list_2 = JobList(jobs=[job_1, job_2b], links=[])
    # noinspection PyTypeChecker
    bus.poll(ClientMock(job_list_2))

    assert obs.records == [
        ("job_added", job_1),
        ("job_added", job_2a),
        ("job_list_changed", job_list_1),
        ("job_changed", job_2b),
        ("job_list_changed", job_list_2),
    ]
    assert bus.get_job("1") == job_1
    assert bus.get_job("2") == job_2b
    assert bus.job_list == job_list_2


def test_job_removed():
    bus = JobsEventBus()

    obs = MyJobsObserver()
    bus.register(obs)

    job_1 = JobInfo(type=JobType.process, jobID="1", status=JobStatus.accepted)
    job_2 = JobInfo(type=JobType.process, jobID="2", status=JobStatus.running)
    job_list_1 = JobList(jobs=[job_1, job_2], links=[])
    # noinspection PyTypeChecker
    bus.poll(ClientMock(job_list_1))

    job_list_2 = JobList(jobs=[job_2], links=[])
    # noinspection PyTypeChecker
    bus.poll(ClientMock(job_list_2))

    assert obs.records == [
        ("job_added", job_1),
        ("job_added", job_2),
        ("job_list_changed", job_list_1),
        ("job_removed", job_1),
        ("job_list_changed", job_list_2),
    ]
    assert bus.get_job("1") is None
    assert bus.get_job("2") == job_2
    assert bus.job_list == job_list_2


def test_job_list_error():
    bus = JobsEventBus()

    obs = MyJobsObserver()
    bus.register(obs)

    # noinspection PyTypeChecker
    bus.poll(ClientMock(None))

    assert obs.records == [("job_list_error", client_error)]


def test_error_in_observer():
    class MyJobsObserverWithError(MyJobsObserver):
        def on_job_list_changed(self, _job_list: JobList):
            raise RuntimeError("Eek!")

    bus = JobsEventBus()

    obs = MyJobsObserverWithError()
    bus.register(obs)

    job_1 = JobInfo(type=JobType.process, jobID="1", status=JobStatus.accepted)
    job_2 = JobInfo(type=JobType.process, jobID="2", status=JobStatus.successful)
    job_list = JobList(jobs=[job_1, job_2], links=[])
    # noinspection PyTypeChecker
    bus.poll(ClientMock(job_list))

    assert obs.records == [
        ("job_added", job_1),
        ("job_added", job_2),
    ]
