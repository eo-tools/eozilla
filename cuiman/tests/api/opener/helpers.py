"""Selected resource/context pairs for opener tests."""

from dataclasses import dataclass

from cuiman.api import JobResultContext
from cuiman.api.config import ClientConfig
from cuiman.api.resolver.impl import ValueResolver
from cuiman.api.resources import JobResultResource
from gavicore.models import JobResults
from gavicore.util.runsync import run_sync


def make_case(
    *,
    config=None,
    job_id="job",
    job_results=None,
    output_name=None,
    data_type=None,
    _media_type=None,
    options=None,
):
    results = (
        job_results if job_results is not None else JobResults(root={"output": None})
    )
    name = output_name or next(iter(results.root))
    value = results.root.get(name)
    resource = run_sync(
        ValueResolver().resolve, JobResultContext(name, value, job_id=job_id)
    )[0]
    context = JobResultContext(
        config=config or ClientConfig(),
        data_type=data_type,
        media_type=_media_type,
        options=options or {},
    )
    return _OpenCase(resource, context, results)


@dataclass
class _OpenCase:
    resource: JobResultResource
    context: JobResultContext
    job_results: JobResults
