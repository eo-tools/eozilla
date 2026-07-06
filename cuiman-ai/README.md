# cuiman-ai

Experimental AI-facing adapters for `cuiman` and OGC API - Processes services.

The first experiment is a thin MCP server that lets an AI client discover and run
processes exposed by a `wraptile` / OGC API - Processes service through the
existing `cuiman.AsyncClient` API.

```text
AI client / MCP host
  -> cuiman-ai MCP server
    -> cuiman.AsyncClient
      -> Wraptile / OGC API - Processes service
        -> jobs and results
```

## Why MCP?

MCP, the Model Context Protocol, gives an AI client a standard way to discover
and call external tools. In this experiment the MCP server does not replace the
OGC API. It is only the AI-facing adapter.

The OGC API remains the processing-service contract. `cuiman-ai` exposes a small
set of MCP tools that call the existing `cuiman` client, which then talks to the
processing service.

## First experiment

This experiment answers one question:

> Can an AI discover available OGC processes, inspect their input schemas,
> execute one process, wait for the job, and summarize the result?

The first version intentionally exposes generic tools instead of one MCP tool per
process. This keeps the adapter small and lets us validate the architecture
before adding dynamic per-process tools.

## Setup

From the repository root, make sure the `cuiman-ai` pixi environment is valid:

```bash
cd ${projects}/eozilla/cuiman-ai
pixi lock --check --no-progress --color never
pixi run check
```

The `check` task currently performs a syntax-level compile check for the package.

## Start a local processing service

In one terminal, start the local Wraptile test service:

```bash
cd ${projects}/eozilla
pixi run wraptile run --port 8008 -- wraptile.services.local.testing:service
```

This exposes an OGC API - Processes service at:

```text
http://127.0.0.1:8008
```

Useful URLs while debugging:

- `http://127.0.0.1:8008/`
- `http://127.0.0.1:8008/processes`
- `http://127.0.0.1:8008/docs`

The test service includes processes such as `sleep_a_while`, `primes_between`,
`simulate_scene`, and `process_pipeline`.

## Start the MCP server

`cuiman-ai` supports three MCP transports:

- `stdio`: useful for local MCP clients that start the server process directly.
- `streamable-http`: useful for ChatGPT, the Responses API, and remote MCP clients.
- `sse`: supported by the underlying MCP SDK for clients that still use HTTP/SSE.

For local stdio inspection, run:

```bash
cd ${projects}/eozilla/cuiman-ai
pixi run cuiman-ai mcp --api-url http://127.0.0.1:8008
```

It is normal for this command to appear to wait forever. A stdio MCP server waits
for an MCP client to send protocol messages on stdin.

For ChatGPT-style local development, run the server with Streamable HTTP:

```bash
cd ${projects}/eozilla/cuiman-ai
pixi run cuiman-ai mcp --transport streamable-http --host 127.0.0.1 --port 8765 --mcp-path /mcp --unsafe-disable-dns-rebinding-protection --api-url http://127.0.0.1:8008
```

This exposes the local MCP endpoint at:

```text
http://127.0.0.1:8765/mcp
```

The dedicated script is equivalent:

```bash
pixi run cuiman-ai-mcp --transport streamable-http --host 127.0.0.1 --port 8765 --mcp-path /mcp --unsafe-disable-dns-rebinding-protection --api-url http://127.0.0.1:8008
```

The API URL can also be provided through `CUIMAN_API_URL`.

Note for development tunnels: FastMCP enables DNS rebinding protection automatically when the server listens on `127.0.0.1`, `localhost`, or `::1`. Public tunnel hostnames such as `*.trycloudflare.com` are not accepted by that default allowlist. For quick local experiments through Cloudflare Tunnel or ngrok, the easiest option is `--unsafe-disable-dns-rebinding-protection`. For a tighter setup, keep protection enabled and pass explicit `--allow-host` and `--allow-origin` values that match the public tunnel hostname and calling origin.

## Configure an MCP host

A local MCP client that can launch stdio servers should use a configuration shaped
like this:

```json
{
  "mcpServers": {
    "cuiman": {
      "command": "pixi",
      "args": [
        "run",
        "cuiman-ai",
        "mcp",
        "--api-url",
        "http://127.0.0.1:8008"
      ],
      "cwd": "C:\\Users\\Norman\\Projects\\eozilla\\cuiman-ai"
    }
  }
}
```

The exact location and format of this configuration depends on the MCP host.

For ChatGPT, use the Streamable HTTP server instead. ChatGPT needs a reachable
HTTPS MCP endpoint, so expose `http://127.0.0.1:8765/mcp` through Secure MCP
Tunnel, ngrok, Cloudflare Tunnel, or another development tunnel. Then create a
ChatGPT connector whose Connector URL points to the public `/mcp` URL, for
example:

```text
https://your-tunnel.example/mcp
```

In ChatGPT, the rough flow is:

```text
Settings -> Apps & Connectors -> Advanced settings -> enable Developer mode
Settings -> Connectors -> Create
Connector URL: https://your-tunnel.example/mcp
```

If the connection succeeds, ChatGPT will show the tools advertised by this MCP
server.

## Exposed MCP tools

The first server exposes generic tools:

- `get_capabilities`: get service landing-page metadata.
- `list_processes`: list available process summaries.
- `describe_process`: get a process description, including input and output schemas.
- `execute_process`: start a process execution and return the created job.
- `list_jobs`: list jobs known to the service.
- `get_job`: get status information for one job.
- `wait_for_job`: poll one job until it reaches a terminal status or times out.
- `get_job_results`: fetch results for a successful job.
- `dismiss_job`: cancel a running job or remove a terminal job.
- `run_process_and_wait`: execute a process, wait for completion, and include results if successful.

## How the AI knows what to do

When an AI host connects to the MCP server, it asks for the available tools. The
MCP server returns each tool's name, description, argument names, type hints, and
JSON schema.

The AI learns process-specific parameters at runtime from the processing service:

```text
list_processes()
describe_process(process_id)
run_process_and_wait(process_id, inputs)
```

For example, to answer "Find primes between 10 and 50", the expected tool flow is:

```text
list_processes()
describe_process("primes_between")
run_process_and_wait(
  process_id="primes_between",
  inputs={"min_val": 10, "max_val": 50}
)
```

`describe_process` returns the OGC process input descriptions and schemas. The AI
uses those schemas to choose input names and values.

## Example prompts

Once the MCP server is connected to an AI host, try prompts like:

```text
List the available cuiman processes.
```

```text
Describe the primes_between process and tell me what inputs it needs.
```

```text
Run primes_between with min_val=10 and max_val=50, wait for completion, and summarize the result.
```

```text
Run sleep_a_while for 2 seconds and show me the final job status.
```

## Current limits

This is deliberately the smallest useful bridge:

- Tools are generic, so the AI must call `describe_process` to learn process-specific inputs.
- There is no dynamic MCP tool generation yet.
- There is no process catalog caching or refresh policy yet.
- The server supports stdio, Streamable HTTP, and SSE transports, but tunnel-friendly host/origin configuration is still development-oriented.
- Authentication is delegated to the existing `cuiman` client configuration.

A later version may expose dynamic per-process tools such as:

```text
run_primes_between(min_val: integer, max_val: integer)
run_sleep_a_while(duration: number, fail: boolean)
```

That would make the AI experience smoother, but it requires converting OGC
process schemas into MCP tool schemas and deciding when to refresh the tool list.

## Development notes

Useful checks:

```bash
cd C:\Users\Norman\Projects\eozilla\cuiman-ai
pixi run check
pixi run python -c "from cuiman_ai.server import create_mcp_server; print(type(create_mcp_server(api_url='http://127.0.0.1:8008')).__name__)"
```

Expected output for the second command includes:

```text
FastMCP
```



