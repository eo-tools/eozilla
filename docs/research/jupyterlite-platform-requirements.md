# JupyterLite platform requirements for the Eozilla work package

Research date: 2026-09-29. This note records platform requirements and proposed
acceptance work, not an executed compatibility certification. Official documentation
was checked; no Eozilla wheels were installed or exercised in a browser for this
research. The `stable` documentation URLs can change, so implementation must record
the exact tested JupyterLite, kernel, Python, Pyodide, and dependency versions.

## Scope boundary

Recommended feature interpretation: make Eozilla's agreed notebook-facing APIs usable
from a browser, including calls to deployed Eozilla services. Explicitly classify
each feature as browser-local, remote-service-backed, or unavailable in the browser.
The browser cannot directly replace a host capable of running Airflow, containers,
shell commands, or listening HTTP servers. This recommendation follows the process,
thread, and socket restrictions below; it is an architectural conclusion, not a
claim that every Eozilla feature has already been tested.

JupyterLite deploys static assets and requires a separately selected kernel.
Its server must deliver WebAssembly with the correct MIME type; HTTPS is recommended.
Source: [JupyterLite standalone deployment](https://jupyterlite.readthedocs.io/en/stable/quickstart/standalone.html).

## Verified platform constraints and resulting work

### Dependencies and distribution

`micropip` installs pure Python wheels and compatible WebAssembly wheels, including
dependencies. A pure Python top-level package can still have incompatible transitive
dependencies. Ordinary Windows/macOS/Linux binary wheels are not a substitute for
WebAssembly builds. Audit the complete runtime dependency graph, optional extras,
version constraints, Python requirements, and import-time side effects.
Source: [Pyodide package loading](https://pyodide.org/en/stable/usage/loading-packages.html).

Native wheels must match the target Python and Pyodide/Emscripten ABI. An available
wheel for a different runtime is insufficient. Where no suitable build exists,
choose a compatible dependency version, remove an unnecessary runtime dependency,
provide an alternative implementation, or budget a maintained WebAssembly build.
Sources: [platform compatibility](https://pyodide-build.readthedocs.io/en/latest/reference/platform.html),
[native build migration](https://pyodide-build.readthedocs.io/en/latest/how-to/migrate.html).

Package delivery can be prepared at site build time with a resolved Pyodide lockfile
or a local wheel index. JupyterLite supports shipping additional wheels and disabling
fallback to public PyPI. Deliver a reproducible installation from a clean browser
session; distinguish runtime packages from desktop-only development/build tools.
Source: [shipping wheels](https://jupyterlite.readthedocs.io/en/stable/howto/pyodide/wheels.html).

JupyterLite also supports Xeus Python with emscripten-forge. Choosing it can change
package availability, but does not remove browser restrictions. Recommend selecting
one reference kernel for the feature and treating support for a second as additional
scope. Source: [JupyterLite package troubleshooting](https://jupyterlite.readthedocs.io/en/stable/troubleshooting.html).

### Networking, authentication, and remote execution

Pyodide's current documentation describes browser support for `requests` and
`urllib3`, with limitations. HTTP still obeys browser CORS rules; TLS, proxy, and
timeout behavior differ from desktop Python. Streaming synchronous responses needs
a worker and cross-origin isolation; otherwise full buffering may occur. Do not
assume that desktop HTTP success or a successful library import establishes browser
compatibility. Source: [Pyodide Python compatibility](https://pyodide.org/en/stable/usage/wasm-constraints.html).

For Eozilla, verify the actual `httpx2` transport and its authentication integration,
including asynchronous calls, polling, cancellation, errors, retries, and result
downloads. That library's compatibility was not established by this research.
Implement a browser-capable transport if required, preserving the existing public
client interface where practical.

Remote API and identity-provider operators must configure CORS for the deployed
notebook origin, methods and headers, including preflight for authenticated calls.
Cookie-based access requires credential-aware client and server settings; wildcard
origins are insufficient for credentialed responses, and third-party-cookie rules
still apply. Expose response headers consumed by the client. Source:
[MDN CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS).

Proposed Eozilla authentication work: replace assumptions about operating-system
keyrings or local callback servers with an agreed browser login/token mechanism;
define session persistence, logout, expiry, and refresh behavior. Ensure distributed
notebooks contain no reusable secrets. Confirm external service changes and service
ownership as feature dependencies. These are implementation recommendations, not a
verified design for Eozilla's identity providers.

### Execution and state

Python threads, multiprocessing, and subprocesses cannot be used as on a desktop in
the documented Pyodide runtime. Browser workers do not make existing Python process
pools work automatically. Inventory background polling, thread pools, subprocess
commands, native executables, file watchers, and servers. Adapt supported local work
to cooperative asynchronous or sequential execution and retain appropriate remote
services for host-dependent work. Sources:
[Pyodide FAQ](https://pyodide.org/en/stable/usage/faq.html),
[migration restrictions](https://pyodide-build.readthedocs.io/en/latest/how-to/migrate.html).

Files in JupyterLite's file browser can be shared with the kernel through
SharedArrayBuffer with COOP/COEP deployment headers, or through a service worker.
Without either, those files are unavailable to the kernel. Validate uploads, generated
outputs, configuration paths, reloads, and downloads against the virtual filesystem.
Source: [kernel filesystem access](https://jupyterlite.readthedocs.io/en/stable/howto/content/python.html).

Service workers require HTTPS or localhost and browser support; Firefox private
browsing is a documented restriction. JupyterLite normally uses persistent browser
storage, commonly IndexedDB, but also supports explicitly volatile memory storage.
Document persistence, export/backup, storage clearing, and supported browser modes.
Sources: [service workers](https://jupyterlite.readthedocs.io/en/stable/howto/configure/advanced/service-worker.html),
[browser storage](https://jupyterlite.readthedocs.io/en/stable/howto/configure/storage.html).

### Optional widgets and visualisation

This is optional notebook integration, not a prerequisite for Eozilla's existing
React/OpenLayers application. Its `remotestate` bridge and local FastAPI/WebSocket
server require a separate browser-to-kernel or remote-service design review.

Jupyter widgets/custom renderers need both kernel-side Python packages and matching
frontend extensions included in the site build. JupyterLite explicitly names
`ipyleaflet` among these cases; ipyleaflet's own documentation offers a JupyterLite
demo. Accordingly it is a validation/integration task, not an assumed blocker.
Test interaction, callbacks, rendering, map tiles, and remote asset loading in the
actual Eozilla examples. Sources:
[JupyterLite extensions](https://jupyterlite.readthedocs.io/en/stable/howto/configure/simple_extensions.html),
[ipyleaflet introduction](https://ipyleaflet.readthedocs.io/en/master/).

### Validation, deployment, and maintenance

Pyodide provides `pytest-pyodide` for tests in browser runtimes; a Pyodide virtual
environment can also exercise WebAssembly under Node.js. Node tests alone cannot
establish browser CORS, UI, authentication, or persistence behavior. Sources:
[Pyodide testing](https://pyodide.org/en/stable/development/testing.html),
[Pyodide virtual environment testing](https://pyodide-build.readthedocs.io/en/latest/how-to/testing.html).

Proposed deliverables and acceptance evidence:

- A feature/dependency matrix covering every package and supported notebook workflow,
  exact versions, supported browsers, remote requirements, and deliberate exclusions.
- Reproducible wheel/site builds and CI tasks integrated with the existing Pixi
  workflow, alongside existing native tests.
- Browser tests for clean installation, imports, model validation, representative
  processing, authentication, job submission/polling/cancellation, result retrieval,
  storage, and supported visualisations. Test failure and recovery paths too.
- A deployed reference JupyterLite site with runnable, small-data examples; explicit
  measurements of initial download, startup, peak memory, and representative runtime.
  Set project-specific limits rather than promising desktop-scale EO processing.
- User documentation for setup-free launch, supported APIs, upload/export, browser
  storage, authentication, remote execution, network troubleshooting, and limitations.
  Developer/operator documentation for builds, tests, dependency updates, deployment
  headers/CORS, release procedure, and maintenance ownership.

Offline use is a separate acceptance choice: runtime and wheels can be bundled, but
remote processing, authentication, map tiles, and external datasets do not thereby
become available offline. Kernel/runtime version compatibility must be retained.
Source: [offline JupyterLite archives](https://jupyterlite.readthedocs.io/en/stable/howto/configure/advanced/offline.html).

## Unresolved verification before a fixed implementation estimate

### Dependency availability snapshot

The official Pyodide 314.0.7 package list includes the following relevant builds:

| Dependency | Listed version |
| --- | --- |
| pydantic / pydantic_core | 2.12.5 / 2.41.5 |
| cryptography | 47.0.0 |
| NumPy / pandas | 2.4.6 / 3.0.2 |
| GeoPandas / Fiona | 1.1.3 / 1.10.1 |
| pyproj / Shapely / Rasterio | 3.7.2 / 2.1.2 / 1.5.0 |
| xarray / Zarr | 2026.2.0 / 3.2.1 |

This is evidence that native dependencies are not automatically blockers. The listed
Pydantic meets Cuiman's `>=2.12` minimum. Listed xarray/Zarr differ from the desktop
workspace's `>=2026.7` and `>=3.1,<3.2` constraints; compatible overrides or adjusted
browser constraints must be verified. Source:
[Pyodide package list](https://pyodide.org/en/stable/usage/packages-in-pyodide.html).

`pydantic-settings==2.14.2` has a pure Python wheel and requires Pydantic `>=2.7.0`,
python-dotenv `>=0.21.0`, and typing-inspection `>=0.4.0`; its minimum version alone
does not establish a conflict with the above Pydantic build. Source:
[release metadata](https://pypi.org/pypi/pydantic-settings/2.14.2/json).

Authlib 1.8.0 has a pure Python wheel and requires cryptography `>=45.0.1` and
joserfc `>=1.6.1`. Listed cryptography meets that minimum, but Eozilla's actual token
and OAuth operations still need browser tests. Source:
[Authlib release metadata](https://pypi.org/pypi/Authlib/1.8.0/json).

HTTPX2's own description names `httpcore2` and `truststore` among its dependencies,
the latter using the operating system's trust store. Compatibility of Pyodide's
listed `httpx` does not prove compatibility of the separately named `httpx2` stack.
Source: [HTTPX2 metadata](https://pypi.org/pypi/httpx2/json).

The local workspace declares dependencies including `pydantic`, `pydantic-settings`,
`httpx2`, `authlib`, `joserfc`, `keyring`, FastAPI/Uvicorn, an Airflow client, and EO
example libraries. These declarations do not prove compatible browser wheels or
behavior. Resolve the exact graph against the selected runtime and exercise the
features actually used. Native/transitive dependencies and authentication/network
paths should be tested early; they can determine whether upstream work, package
splitting, or additional hosted components are required.

No whole-package or exact-version compatibility guarantee is made here. The feature
should include an early feasibility milestone and a bounded decision on any required
native ports or server-dependent features before committing to unrestricted parity.
