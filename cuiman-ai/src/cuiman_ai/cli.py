from __future__ import annotations

from typing import Annotated

import typer

from .server import TransportName, run_mcp_server

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="AI-facing adapters for cuiman services.",
)


@app.callback()
def app_callback() -> None:
    """AI-facing adapters for cuiman services."""


@app.command("mcp")
def run_mcp_command(
    api_url: Annotated[
        str | None,
        typer.Option(
            "--api-url",
            envvar="CUIMAN_API_URL",
            help="Base URL of the OGC API - Processes service.",
        ),
    ] = None,
    config_path: Annotated[
        str | None,
        typer.Option(
            "--config-path",
            envvar="CUIMAN_CONFIG_PATH",
            help="Optional cuiman client configuration file.",
        ),
    ] = None,
    transport: Annotated[
        TransportName,
        typer.Option(
            "--transport",
            help="MCP transport: stdio, sse, or streamable-http.",
        ),
    ] = "stdio",
    host: Annotated[
        str,
        typer.Option(
            "--host",
            envvar="CUIMAN_AI_MCP_HOST",
            help="Host for HTTP MCP transports.",
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            envvar="CUIMAN_AI_MCP_PORT",
            help="Port for HTTP MCP transports.",
        ),
    ] = 8000,
    mcp_path: Annotated[
        str,
        typer.Option(
            "--mcp-path",
            envvar="CUIMAN_AI_MCP_PATH",
            help="Streamable HTTP MCP endpoint path.",
        ),
    ] = "/mcp",
    sse_path: Annotated[
        str,
        typer.Option(
            "--sse-path",
            envvar="CUIMAN_AI_SSE_PATH",
            help="SSE MCP endpoint path.",
        ),
    ] = "/sse",
    dns_rebinding_protection: Annotated[
        bool,
        typer.Option(
            "--dns-rebinding-protection/--unsafe-disable-dns-rebinding-protection",
            help=(
                "Enable or disable FastMCP DNS rebinding protection. Disable only "
                "for development tunnels or trusted reverse proxies."
            ),
        ),
    ] = True,
    allowed_hosts: Annotated[
        list[str] | None,
        typer.Option(
            "--allow-host",
            envvar="CUIMAN_AI_ALLOWED_HOSTS",
            help="Additional allowed Host header values for HTTP MCP transports.",
        ),
    ] = None,
    allowed_origins: Annotated[
        list[str] | None,
        typer.Option(
            "--allow-origin",
            envvar="CUIMAN_AI_ALLOWED_ORIGINS",
            help="Additional allowed Origin header values for HTTP MCP transports.",
        ),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug/--no-debug",
            help="Enable debug logging in the underlying cuiman HTTP transport.",
        ),
    ] = False,
) -> None:
    """Run the cuiman MCP server."""
    try:
        run_mcp_server(
            api_url=api_url,
            config_path=config_path,
            debug=debug,
            transport=transport,
            host=host,
            port=port,
            streamable_http_path=mcp_path,
            sse_path=sse_path,
            dns_rebinding_protection=dns_rebinding_protection,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def main() -> None:
    app()


def mcp_main() -> None:
    typer.run(run_mcp_command)
