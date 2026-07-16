from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

from cuiman import AsyncClient, ClientError
from gavicore.models import JobInfo, ProcessRequest
from pydantic import BaseModel

JsonObject = dict[str, Any]
ResponseTypeName = Literal["raw", "document"]

TERMINAL_JOB_STATUSES = {"successful", "failed", "dismissed"}


class CuimanBridge:
    """Small async facade used by the MCP tools."""

    def __init__(
        self,
        *,
        api_url: str | None = None,
        config_path: str | None = None,
        debug: bool = False,
    ):
        self._client = AsyncClient(
            api_url=api_url,
            config_path=config_path,
            _debug=debug,
        )

    async def close(self) -> None:
        await self._client.close()

    async def get_capabilities(self) -> JsonObject:
        return to_jsonable(await self._client.get_capabilities())

    async def list_processes(self) -> JsonObject:
        return to_jsonable(await self._client.get_processes())

    async def describe_process(self, process_id: str) -> JsonObject:
        return to_jsonable(await self._client.get_process(process_id))

    async def execute_process(
        self,
        process_id: str,
        *,
        inputs: JsonObject | None = None,
        outputs: JsonObject | None = None,
        response: ResponseTypeName = "raw",
    ) -> JsonObject:
        request = ProcessRequest(
            inputs=inputs or None,
            outputs=outputs or None,
            response=response,
        )
        return to_jsonable(await self._client.execute_process(process_id, request))

    async def list_jobs(self) -> JsonObject:
        return to_jsonable(await self._client.get_jobs())

    async def get_job(self, job_id: str) -> JsonObject:
        return to_jsonable(await self._client.get_job(job_id))

    async def dismiss_job(self, job_id: str) -> JsonObject:
        return to_jsonable(await self._client.dismiss_job(job_id))

    async def get_job_results(self, job_id: str) -> JsonObject | None:
        return to_jsonable(await self._client.get_job_results(job_id))

    async def run_process_and_wait(
        self,
        process_id: str,
        *,
        inputs: JsonObject | None = None,
        outputs: JsonObject | None = None,
        response: ResponseTypeName = "raw",
        timeout_seconds: float = 300.0,
        poll_interval_seconds: float = 1.0,
    ) -> JsonObject:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be greater than or equal to 0")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than 0")

        job = await self.execute_process(
            process_id,
            inputs=inputs,
            outputs=outputs,
            response=response,
        )
        job_id = job["jobID"]
        final_job = await self.wait_for_job(
            job_id,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        result: JsonObject = {"job": final_job}
        if final_job.get("status") == "successful":
            result["results"] = await self.get_job_results(job_id)
        return result

    async def wait_for_job(
        self,
        job_id: str,
        *,
        timeout_seconds: float = 300.0,
        poll_interval_seconds: float = 1.0,
    ) -> JsonObject:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be greater than or equal to 0")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than 0")

        deadline = time.monotonic() + timeout_seconds
        while True:
            job = await self._client.get_job(job_id)
            status = get_job_status(job)
            job_data = to_jsonable(job)
            if status in TERMINAL_JOB_STATUSES:
                return job_data
            if time.monotonic() >= deadline:
                job_data["timedOut"] = True
                return job_data
            await asyncio.sleep(poll_interval_seconds)


def get_job_status(job: JobInfo) -> str:
    status = job.status
    return status.value if hasattr(status, "value") else str(status)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
        )
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if hasattr(value, "value"):
        return value.value
    return value


def format_client_error(error: ClientError) -> JsonObject:
    api_error = getattr(error, "api_error", None)
    return {
        "type": type(error).__name__,
        "message": str(error),
        "apiError": to_jsonable(api_error) if api_error is not None else None,
    }
