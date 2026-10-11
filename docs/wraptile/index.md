# Wraptile

Eozilla _Wraptile_ is a server made for wrapping workflow orchestration 
systems with a unified restful API that should be almost compliant
with the [OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes).

Wraptile can currently be run with a local execution service or with Airflow.

HTTP routes follow the OGC API - Processes specification parts:

```text
wraptile/
  routes/
    __init__.py
    core.py
    dru.py
```

`wraptile.routes.core` defines Part 1: Core endpoints for process discovery,
execution, and jobs. Importing `wraptile.main` registers these endpoints on
the FastAPI application.

`wraptile.routes.dru` defines Part 2: Deploy, Replace, Undeploy endpoints,
including application-package retrieval. It also owns
`OgcApplicationPackageResponse`, which sets the response media type to
`application/ogcapppkg+json`. DRU endpoints are registered only when a
`DruService` implementation is loaded.

Tests mirror the route modules in `wraptile/tests/routes/test_core.py` and
`wraptile/tests/routes/test_dru.py`. Application lifecycle and logging tests
remain in `wraptile/tests/test_app.py`.

