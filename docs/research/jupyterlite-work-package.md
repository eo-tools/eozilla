# Eozilla JupyterLite compatibility work package

Planning assessment, 29 September 2026. Based on the current local source,
package metadata, notebooks, documentation, and official platform documentation.
This is a scope assessment, not a claim that installation or execution has been
verified in JupyterLite. See the accompanying
[platform research](jupyterlite-platform-requirements.md) for external sources.

## Work package overview

Adapt the Eozilla suite for use from JupyterLite, providing a reproducible
browser-based Python environment for process and workflow authoring, schema
validation, lightweight execution, interaction with remote OGC API - Processes
services, supported result inspection, and integrated graphical interaction.
The work includes dependency qualification and packaging, browser runtime and
authentication adaptations, notebook and GUI integration, automated browser
testing, a deployable reference environment, and updated user, developer, and
deployment documentation. Server execution, orchestration, and container builds
remain external services, with their browser-facing integration explicitly
defined and tested.

## Scope boundary to put in the contract

“All packages compatible” must specify capabilities, not merely successful
installation or imports. Use a matrix with three outcomes: runs in the browser,
is accessed remotely, or is explicitly unavailable with a documented alternative.
Approve this matrix at the first milestone. The proposed baseline below covers
every suite component; it does not promise desktop execution parity.

JupyterLite's Pyodide kernel runs Python inside the browser. Native listening
servers, ordinary Python threading/multiprocessing, subprocesses, Docker, and
Airflow are not facilities a standard deployment provides. A browser can still
call remote services, and in-process service logic can potentially be adapted.
Hosting a real Wraptile server inside the browser would require a separately
specified architecture, rather than just dependency changes.

## Package-specific work

| Component | Proposed supported outcome and required work |
| --- | --- |
| Gavicore | Validate and serialize OGC models and schemas; qualify Pydantic and YAML dependencies. Adapt or bypass the background-thread implementation of `run_sync` for browser execution and document the asynchronous API contract. Audit filesystem and dynamic import utilities. |
| Procodile | Author, register, validate, and execute small compatible processes/workflows. Replace thread-based callback reporting with an appropriate browser implementation; define progress, cancellation, and artifact handling. Qualify dependencies of the actual example processors separately. DOT generation is ordinary text output; graphical rendering needs a browser-compatible renderer if included. |
| Appligator | Generate DAG source, Dockerfiles, and configuration in the virtual filesystem and export/download the bundle. Separate generation from Docker builds and external deployment. Check access to bundled templates and source discovery for functions defined in notebook cells; the current image helper assumes importable source files. |
| Cuiman | Qualify/adapt HTTP transport and authentication for browser networking; support remote discovery, execution, job polling, cancellation, results, and failures. Provide an asynchronous notebook path without thread-dependent helpers. Adapt configuration, credential lifecycle, and supported result openers. |
| Wraptile | Enable remote Wraptile access from JupyterLite and qualify reusable library components. If local service demonstrations are required, build an explicit in-process/cooperative execution adapter: current local execution uses thread or process pools. Keep listening HTTP servers and production executors on external infrastructure. |
| Eozilla umbrella package | Define a supported browser installation and import experience. It currently depends on every suite package and imports them all. Restructure dependency groups/distributions and import boundaries as needed while preserving desktop installation. |
| Eozilla App | Deliver static assets and a notebook display integration; replace or adapt Cuiman's local FastAPI/WebSocket/RemoteState bridge. Preserve agreed Python-to-GUI state synchronization, service selection, authentication, schema forms, and result presentation. Reuse the existing browser service-provider architecture where suitable. |
| Eozilla Airflow environment | Keep Airflow/Kubernetes execution external; provide a notebook that submits and monitors a remote workflow. This is a Linux/Python 3.12 integration environment, not one of the six main distributable suite packages. |
| Examples and CLI | Port selected `procodile-example` and Cuiman examples. Replace notebook shell commands with Python calls, or explicitly scope a tested in-process CLI invocation where useful. A shell and executable entry points are not assumed. |

Repository evidence: [package manifests](../../pyproject.toml),
[Cuiman dependencies](../../cuiman/pyproject.toml),
[thread-based sync bridge](../../gavicore/src/gavicore/util/runsync.py),
[callback reporter](../../procodile/src/procodile/reporter.py),
[local executor](../../wraptile/src/wraptile/services/local/local_service.py),
[Docker build helper](../../appligator/src/appligator/airflow/gen_image.py),
[Cuiman GUI server](../../cuiman/src/cuiman/app/serve.py), and
[umbrella imports](../../eozilla/src/eozilla/__init__.py).

## Tasks and deliverables

1. **Compatibility baseline and feasibility proof.** Select and pin JupyterLite,
   its Python kernel, Pyodide, Python, and supported browsers. Inventory every
   direct and transitive runtime dependency and optional feature. Record wheel
   availability, versions, imports, representative execution, licensing, and
   remediation. Prove the critical Pydantic, HTTP, authentication, and GUI paths
   before committing to a fixed implementation estimate. Deliver a capability
   matrix and evidence-backed backlog.

2. **Dependency and packaging adaptation.** Build/install Eozilla wheels in the
   chosen environment. Qualify pure-Python dependencies as well as native ones;
   ordinary Linux/Windows wheels and the existing desktop Pixi lock are not
   browser artifacts. Resolve missing compatible wheels through version
   alignment, alternatives, or explicitly budgeted WebAssembly builds. Make
   desktop/server integrations optional at both dependency and import levels.
   Adding a `lite` extra alone cannot remove existing mandatory dependencies.
   Publish or bundle a reproducible set of wheels and assets, retaining Pixi
   for build and development tasks.

3. **Runtime and network adaptation.** Use browser-compatible asynchronous
   requests and cooperative scheduling. Test the actual `httpx2` stack and
   Authlib integration rather than assuming HTTPX adapters apply unchanged.
   Cover timeouts, cancellation, pagination, job lifecycle, downloads, and
   cleanup. Validate HTTPS, CORS preflight, permitted/exposed headers, redirects,
   and result-storage origins against real reference services. Wraptile already
   has CORS middleware; verify its behavior and infrastructure configuration
   instead of treating CORS as absent. A browser cannot fix a remote service's
   restrictive CORS policy; a hosted proxy, if needed, is an explicit deployment
   dependency.

4. **Authentication and configuration.** Replace loopback callback servers,
   interactive terminal prompts, and OS keyring assumptions. Specify browser
   public-client OAuth/OIDC with PKCE and registered redirects, or a separately
   hosted credential-owning backend where required. Reuse the app's existing
   browser authentication where practical. Test login, refresh, expiry,
   cancellation, logout, and session isolation. Browser code cannot retain a
   confidential client secret. Define credential lifetime and persistence;
   browser storage is not equivalent to the OS keyring. Preserve the current
   desktop behavior and avoid placing credentials in distributed notebooks,
   URLs, or generated static assets.

5. **GUI and notebook integration.** Provide a working `launch_app` equivalent
   for JupyterLite with agreed state exchange between kernel and React UI.
   Choose and test a kernel message/comm or JavaScript bridge, or an explicitly
   hosted backend. Test reload/restart cleanup, iframe origin rules, authentication
   redirects/popups, themes, and asset paths. The standalone app is already a
   browser application; embedding it alone does not reproduce the current
   Python-integrated experience. Changes span the nested app repository and
   the Cuiman package and need coordinated releases.

6. **Files, scientific data, and examples.** Support uploads, virtual paths,
   persistence, downloads, and artifact export without shared host/server disk
   assumptions. Define a tested format matrix for image, table, vector, and
   array results. Verify each backend/codec and remote access method, not just
   imports of pandas, GeoPandas, or xarray. Use browser-compatible fetching or
   downloadable bytes where readers expect local files. Test authenticated
   result links, object storage access, range/chunk reads where needed, and
   practical memory/data-size limits. Convert localhost and `file://` examples
   to bundled fixtures or remote HTTPS resources. Provide small, reproducible
   workflows; arbitrary third-party EO processors are outside an automatic
   blanket compatibility guarantee.

7. **Reference distribution, CI, and release.** Add a reproducible JupyterLite
   build and static deployment configuration with pinned packages, notebooks,
   assets, and a documented package-loading strategy. Select supported hosting
   headers/service-worker behavior and verify filesystem synchronization.
   Add real-browser CI using the deployed kernel and built wheels, alongside
   existing desktop checks and tests. Measure cold-start size/time and agreed
   representative workloads. Include cache updates, kernel resets, browser
   versions, failure diagnostics, and maintenance instructions. Offline use is
   an additional explicit requirement: static hosting alone does not provide it.

8. **Documentation and handover.** Publish a JupyterLite quickstart and launch
   link, capability/dependency/format matrix, installation and upgrade guidance,
   API examples using `await`, authentication instructions, filesystem and
   persistence explanation, troubleshooting, and hosting/CI guidance. Update
   README/package installation guidance; Cuiman getting-started, configuration,
   authentication, GUI-generation and guides; relevant Gavicore/Procodile/
   Appligator/Wraptile pages; and `docs/eozilla-app/` for app changes. Refresh
   relevant `notebooks/` and maintained `examples/guides/cuiman/`, avoiding
   contradictory desktop assumptions. Update MkDocs navigation, contribution
   guidance, changelog, and release notes. Build docs with `pixi run build-docs`.

## Dependencies requiring explicit qualification

The researched official Pyodide package list already includes Pydantic 2.12.5,
its matching core, cryptography, and several geospatial libraries. Native code
is therefore not an automatic blocker. Its listed xarray 2026.2.0 and Zarr
3.2.1 differ from this workspace's constraints (`>=2026.7` and `>=3.1,<3.2`).
Choose and test browser-specific versions instead of assuming the desktop lock
can be reused. This availability snapshot is not a tested JupyterLite release
combination. Source: [official package list](https://pyodide.org/en/stable/usage/packages-in-pyodide.html).

- **Shared model stack:** Pydantic's compiled `pydantic-core` and matching
  Pydantic/settings versions. Cuiman currently requires `pydantic >=2.12` and
  `pydantic-settings >=2.14.2`; test these exact constraints against the selected
  Pyodide package set rather than assuming compatibility from the package name.
- **Supporting libraries:** PyYAML, Jinja2/MarkupSafe, tomli-w, Typer and its
  dependencies, URI templates, and IPython. Installation, terminal behavior,
  templates, and rich notebook display need separate validation as applicable.
- **Network/authentication:** `httpx2`, `httpcore2`, and the OS-oriented
  `truststore` dependency; Authlib, joserfc,
  cryptography and transitive native dependencies; `keyring` needs a browser
  alternative for its desktop function.
- **GUI/server stack:** RemoteState, FastAPI, Starlette, AnyIO, Uvicorn and
  WebSocket-related dependencies. The locked RemoteState 0.3.4 wheel requires
  Python >=3.12 and brings FastAPI and Uvicorn into Cuiman transitively. A
  pure-Python wheel does not establish that its server behavior is available.
- **Optional data stack:** NumPy, Pillow, pandas, xarray, Zarr/numcodecs,
  GeoPandas/Shapely/pyproj and selected file drivers; Parquet/Arrow,
  HDF5/NetCDF, Excel engines, fsspec/S3 clients, and Dask as required by the
  agreed demonstrations. Include only tested combinations and scheduler modes.
- **Build-only/server tools:** Hatch, Pixi, Node/Vite, MkDocs, Airflow,
  Kubernetes and Docker remain in build or remote execution environments.
  Do not attempt to load the entire desktop development environment in Pyodide.

## Acceptance criteria and milestones

- **M1 — baseline accepted:** all packages/features and dependencies classified,
  selected runtime versions pinned, critical feasibility tests recorded, and
  browser-versus-remote execution boundaries approved.
- **M2 — functional integration:** a clean browser can install/load the agreed
  distributions, validate models, run a small local workflow, export an
  application bundle, and discover/submit/monitor/cancel a remote OGC job.
  Authentication and GUI interaction pass the agreed scenarios; representative
  image/table/vector/array results open in each promised format.
- **M3 — release and handover:** reference site/build delivered; browser CI,
  existing relevant desktop tests/checks, and strict documentation build pass;
  data persistence/reset and negative paths are tested; performance results and
  supported limits are documented; user and maintainer guidance is complete.

Do not accept import-only smoke tests or a standalone GUI demonstration as
proof of complete compatibility. Add meaningful behavioral tests and retain
the repository's high coverage expectation for touched code; inspect relevant
Cuiman test coverage before implementation.

The main effort uncertainties are native/transitive dependency gaps, authentication
provider requirements, replacement of the local GUI bridge, and the breadth of
scientific formats and local execution promised. Budget these explicitly and
refine estimates after M1. New hosted proxy/build infrastructure, arbitrary
processor ports, offline delivery, or full native server parity should be
separately priced options rather than implicit commitments.
