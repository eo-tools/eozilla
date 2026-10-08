import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from cuiman.api import JobResultContext
from cuiman.api.config import ClientConfig
from cuiman.api.exceptions import ClientWarning
from cuiman.api.opener import JobResultOpener, JobResultOpenError
from cuiman.api.opener.opener import open_job_result
from cuiman.api.resources import JobResultResource


@pytest.mark.asyncio
async def test_dispatch_precedence_selected_values_and_options_are_isolated():
    resource = JobResultResource(
        id="selected", output_name="x", kind="value", value=None
    )
    context = JobResultContext(
        config=ClientConfig(), options={"nested": {"original": True}}
    )

    class Reject(JobResultOpener):
        async def accept(self, resource, *, context):
            context.options["nested"]["original"] = False
            return False

        async def open(self, resource, *, context):
            raise AssertionError("Rejected opener was invoked")

    class Accept(JobResultOpener):
        async def accept(self, selected, *, context):
            assert selected is resource
            assert context.options["nested"] == {"original": True}
            return selected.has_value

        async def open(self, selected, *, context):
            return selected.value

    assert (
        await open_job_result(resource, Reject, Accept, _Failure, context=context)
        is None
    )
    assert context.options == {"nested": {"original": True}}


@pytest.mark.asyncio
async def test_acceptance_and_environment_errors_allow_later_candidates():
    resource, context = _selected()
    with patch.object(
        _Success, "accept", new=AsyncMock(side_effect=KeyError("SECRET"))
    ):
        with pytest.warns(ClientWarning, match="KeyError") as recorded:
            assert (
                await open_job_result(
                    resource, _Success, _Failure, _Success2, context=context
                )
                == 137
            )
        assert "SECRET" not in str(recorded[0].message)
    with patch.object(_Success, "is_usable", side_effect=ValueError("SECRET")):
        with pytest.warns(ClientWarning, match="ValueError"):
            assert (
                await open_job_result(resource, _Success, _Success2, context=context)
                == 137
            )


@pytest.mark.asyncio
async def test_failure_group_counts_only_accepted_openers():
    resource, context = _selected()
    with patch.object(_Success, "accept", new=AsyncMock(return_value=False)):
        with pytest.raises(
            JobResultOpenError, match="_Failure: FileNotFoundError"
        ) as raised:
            await open_job_result(resource, _Success, _Failure, context=context)
    assert "SECRET" not in str(raised.value)
    assert (
        str(raised.value.__cause__) == "1 of 1 possible opener failed (1 sub-exception)"
    )
    with pytest.raises(JobResultOpenError) as raised:
        await open_job_result(resource, _Failure, _Failure, context=context)
    assert len(raised.value.__cause__.exceptions) == 2


@pytest.mark.asyncio
async def test_no_candidates_unusable_candidates_and_invalid_entries():
    resource, context = _selected()
    with pytest.raises(JobResultOpenError, match="No job result openers provided"):
        await open_job_result(resource, context=context)
    with patch.object(_Success, "is_usable", return_value=False):
        with pytest.raises(JobResultOpenError, match="No job result opener found"):
            await open_job_result(resource, _Success, context=context)
    with pytest.raises(TypeError, match="compatible with JobResultOpener"):
        await open_job_result(resource, 123, context=context)


@pytest.mark.asyncio
async def test_cancellation_propagates_during_acceptance_and_opening():
    resource, context = _selected()
    for method in ["accept", "open"]:
        with patch.object(
            _Success, method, new=AsyncMock(side_effect=asyncio.CancelledError)
        ):
            with pytest.raises(asyncio.CancelledError):
                await open_job_result(resource, _Success, context=context)


class _Success(JobResultOpener):
    async def accept(self, resource, *, context):
        return True

    async def open(self, resource, *, context):
        return 137


class _Success2(_Success):
    @classmethod
    def is_usable(cls):
        return True

    async def accept(self, resource, *, context):
        return True


class _Failure(_Success):
    async def accept(self, resource, *, context):
        return True

    async def open(self, resource, *, context):
        raise FileNotFoundError("SECRET")


def _selected():
    return JobResultResource(
        id="resource", output_name="x", kind="value", value=137
    ), JobResultContext(config=ClientConfig())
