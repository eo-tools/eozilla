from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypeAlias, TypeVar

from cuiman import ClientError
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .bridge import CuimanBridge, format_client_error

T = TypeVar("T")
JsonObject = dict[str, Any]
ResponseTypeName = Literal["raw", "document"]
TransportName: TypeAlias = Literal["stdio", "sse", "streamable-http"]


def create_mcp_server(
    *,
    api_url: str | None = None,
    config_path: str | None = None,
    debug: bool = False,
    name: str = "cuiman-ai",
    host: str = "127.0.0.1",
    port: int = 8000,
    streamable_http_path: str = "/mcp",
    sse_path: str = "/sse",
    dns_rebinding_protection: bool = True,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
) -> FastMCP:
    """Create the cuiman MCP server and register its tools."""

    bridge = CuimanBridge(api_url=api_url, config_path=config_path, debug=debug)
    transport_security = _build_transport_security(
        host=host,
        dns_rebinding_protection=dns_rebinding_protection,
        allowed_hosts=allowed_hosts or [],
        allowed_origins=allowed_origins or [],
    )
    mcp = FastMCP(
        name,
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        sse_path=sse_path,
        transport_security=transport_security,
        instructions=(
            "Use list_processes to discover available OGC API - Processes, "
            "describe_process to inspect input and output schemas, and "
            "run_process_and_wait for ordinary process execution requests."
        ),
    )

    @mcp.tool()
    async def get_capabilities() -> JsonObject:
        """Get the OGC API - Processes service landing page metadata."""
        return await _safe_call(bridge.get_capabilities)

    @mcp.tool()
    async def list_processes() -> JsonObject:
        """List process summaries exposed by the configured processing service."""
        return await _safe_call(bridge.list_processes)

    @mcp.tool()
    async def describe_process(process_id: str) -> JsonObject:
        """Get a process description, including input and output schemas.

        Args:
            process_id: Exact process identifier from list_processes.
        """
        return await _safe_call(bridge.describe_process, process_id)

    @mcp.tool()
    async def execute_process(
        process_id: str,
        inputs: JsonObject | None = None,
        outputs: JsonObject | None = None,
        response: ResponseTypeName = "raw",
    ) -> JsonObject:
        """Start a process execution and return the created job.

        Use describe_process first if you do not know the accepted inputs.

        Args:
            process_id: Exact process identifier from list_processes.
            inputs: JSON object mapping process input names to values.
            outputs: Optional JSON object describing desired outputs.
            response: OGC response mode, either raw or document.
        """
        return await _safe_call(
            bridge.execute_process,
            process_id,
            inputs=inputs,
            outputs=outputs,
            response=response,
        )

    @mcp.tool()
    async def list_jobs() -> JsonObject:
        """List jobs known to the configured processing service."""
        return await _safe_call(bridge.list_jobs)

    @mcp.tool()
    async def get_job(job_id: str) -> JsonObject:
        """Get status information for a job.

        Args:
            job_id: Job identifier returned by execute_process or list_jobs.
        """
        return await _safe_call(bridge.get_job, job_id)

    @mcp.tool()
    async def wait_for_job(
        job_id: str,
        timeout_seconds: float = 300.0,
        poll_interval_seconds: float = 1.0,
    ) -> JsonObject:
        """Poll a job until it reaches a terminal status or times out.

        Args:
            job_id: Job identifier returned by execute_process or list_jobs.
            timeout_seconds: Maximum number of seconds to wait.
            poll_interval_seconds: Delay between status checks.
        """
        return await _safe_call(
            bridge.wait_for_job,
            job_id,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    @mcp.tool()
    async def get_job_results(job_id: str) -> JsonObject:
        """Get results for a successful job.

        Args:
            job_id: Job identifier returned by execute_process or list_jobs.
        """
        return await _safe_call(bridge.get_job_results, job_id)

    @mcp.tool()
    async def dismiss_job(job_id: str) -> JsonObject:
        """Cancel a running job or remove a terminal job from the service job list.

        Args:
            job_id: Job identifier returned by execute_process or list_jobs.
        """
        return await _safe_call(bridge.dismiss_job, job_id)

    @mcp.tool()
    async def run_process_and_wait(
        process_id: str,
        inputs: JsonObject | None = None,
        outputs: JsonObject | None = None,
        response: ResponseTypeName = "raw",
        timeout_seconds: float = 300.0,
        poll_interval_seconds: float = 1.0,
    ) -> JsonObject:
        """Execute a process, wait for completion, and include results if successful.

        Args:
            process_id: Exact process identifier from list_processes.
            inputs: JSON object mapping process input names to values.
            outputs: Optional JSON object describing desired outputs.
            response: OGC response mode, either raw or document.
            timeout_seconds: Maximum number of seconds to wait.
            poll_interval_seconds: Delay between status checks.
        """
        return await _safe_call(
            bridge.run_process_and_wait,
            process_id,
            inputs=inputs,
            outputs=outputs,
            response=response,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    return mcp


def run_mcp_server(
    *,
    api_url: str | None = None,
    config_path: str | None = None,
    debug: bool = False,
    transport: TransportName = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    streamable_http_path: str = "/mcp",
    sse_path: str = "/sse",
    dns_rebinding_protection: bool = True,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
) -> None:
    server = create_mcp_server(
        api_url=api_url,
        config_path=config_path,
        debug=debug,
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        sse_path=sse_path,
        dns_rebinding_protection=dns_rebinding_protection,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )
    server.run(transport=transport)


def _build_transport_security(
    *,
    host: str,
    dns_rebinding_protection: bool,
    allowed_hosts: list[str],
    allowed_origins: list[str],
) -> TransportSecuritySettings | None:
    if not dns_rebinding_protection:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    local_host = host in ("127.0.0.1", "localhost", "::1")
    if not local_host and not allowed_hosts and not allowed_origins:
        return None

    merged_hosts = _unique_preserving_order(
        [
            *(["127.0.0.1:*", "localhost:*", "[::1]:*"] if local_host else []),
            *allowed_hosts,
        ]
    )
    merged_origins = _unique_preserving_order(
        [
            *(
                ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
                if local_host
                else []
            ),
            *allowed_origins,
        ]
    )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=merged_hosts,
        allowed_origins=merged_origins,
    )


def _unique_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


async def _safe_call(
    call: Callable[..., Awaitable[T]],
    *args: Any,
    **kwargs: Any,
) -> JsonObject:
    try:
        return {"ok": True, "data": await call(*args, **kwargs)}
    except ClientError as error:
        return {"ok": False, "error": format_client_error(error)}
    except Exception as error:
        return {
            "ok": False,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
