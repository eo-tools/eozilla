# Cuiman guide examples

These files supply the snippets in `docs/cuiman/guides/`. They use the current
Cuiman interfaces and are independent of the historical notebooks in `notebooks/`.
Imports do not connect to services or submit jobs.

From the repository root, run `pixi install`, start `pixi run serve` in one
terminal, and use `pixi shell` in another:

- `python -m examples.guides.cuiman.api`: submit a prime-number job, inspect its
  status once, and close the client. Retain the returned job ID if still running.
- `python -m examples.guides.cuiman.app`: open the browser App and keep its server
  alive until Ctrl+C. In a notebook, import `open_app`, `set_duration`, and
  `close_app`; call `open_app(display="notebook")` and retain its two handles.
- `python -m examples.guides.cuiman.openers`: submit a small simulated scene and
  open its Zarr output with the built-in reader. The custom opener is an optional
  alternative demonstrated separately in the guide.
- `cli.sh`: individual command recipes for Bash or PowerShell. Running the file
  exits without executing them. Configure updates the saved profile, submit
  creates a job, and dismiss cancels or deletes the selected job.
- `simulate-scene-request.json`: shared API/CLI request. Choose an unused output
  path before running; the local server overwrites a dataset at that location.
  File paths are relative to the server, and the client must share its filesystem.

Python examples explicitly select the unauthenticated local service at
`http://127.0.0.1:8008`. Adapt configuration and login for other deployments.
The full scripts close their clients in `finally`; interactive sessions should
use the cleanup calls shown in the guides.

## Maintenance

Run `pixi run format`, `pixi run checks`, `pixi run test-cuiman`, and
`pixi run build-docs`. Tests run offline using mocks, real App state, and small
temporary Zarr datasets produced by the local process implementation. They check
job-ID reuse, successful-result gating, request validity, cleanup, and opener
registration. Example source is included in Cuiman coverage.

Keep snippet names stable. Documentation builds validate includes but never
execute examples. Inspect the rendered guides with `pixi run serve-docs`.

## Static image provenance

- `docs/assets/guides/cuiman/process-inputs.png`: captured September 16, 2026
  from the App bundled with this Eozilla checkout (version 0.1.2-dev.0, build 44), connected to
  `wraptile.services.local.testing:service` on the same machine. It shows the
  Sleep Processor with duration 2 and failure disabled. No personal service
  configuration or credentials are used.

To refresh, start `pixi run serve`, launch `open_app()` from `app.py`, choose
Sleep Processor, set duration to 2 and leave fail disabled, then capture the
process form. Keep screenshots free of launch URLs and record the capture date
and any changed setup here. Commit the image; MkDocs does not regenerate it.
