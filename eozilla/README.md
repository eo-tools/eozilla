[![CI](https://github.com/eo-tools/eozilla/actions/workflows/ci.yml/badge.svg)](https://github.com/eo-tools/eozilla/actions/workflows/ci.yml)
[![Codecov](https://codecov.io/gh/eo-tools/eozilla/graph/badge.svg?token=T3EXHBMD0G)](https://codecov.io/gh/eo-tools/eozilla)
[![Pixi](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![License](https://img.shields.io/github/license/eo-tools/eozilla)](https://github.com/eo-tools/eozilla)

# Eozilla

A suite of tools around workflow orchestration systems and the
[OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes).

_Note, this project and its documentation is still in an early development stage._

The `eozilla` package bundles the Eozilla suite of tools:

* `cuiman`: A Python client including API, GUI, and CLI for servers 
   compliant with _OGC API - Processes_.
* `wraptile`: A fast and lightweight HTTP server that implements _OGC API - Processes_
   for various workflow processing backends, such Airflow or a local executor.
* `procodile`: A simple Python framework for registering and executing processes.
* `appligator`: An EO application bundler and transformer. 
   (Currently limited to generating Airflow DAGs.)
* `gavicore`: Common pydantic data models and utilities for the packages above.

Large parts of the work in the Eozilla project has been made possible by the 
[ESA DTE-S2GOS project](https://dte-s2gos.rayference.eu/about/).
