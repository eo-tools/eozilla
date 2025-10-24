[![CI](https://github.com/eo-tools/eozilla/actions/workflows/ci.yml/badge.svg)](https://github.com/eo-tools/eozilla/actions/workflows/ci.yml)
[![Codecov](https://codecov.io/gh/eo-tools/eozilla/graph/badge.svg?token=T3EXHBMD0G)](https://codecov.io/gh/eo-tools/eozilla)
[![Pixi](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![License](https://img.shields.io/github/license/eo-tools/eozilla)](https://github.com/eo-tools/eozilla)

# Eozilla

Eozilla is a suite of tools for workflow orchestration systems and
[OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes)
implementation.

Eozilla has been developed to cloudify satellite data processor applications and 
run them in the cloud.

_Note: this project and its documentation are still in an early development stage._

## Features

The Eozilla suite of tools comprises:

* `procodile`: A simple Python framework for registering and executing processes.
* `appligator`: An EO application bundler and transformer.
   (Currently limited to generating Airflow DAGs.)
* `wraptile`: A fast and lightweight HTTP server that implements _OGC API - Processes_
   for various workflow processing backends, such Airflow or a local executor.
* `cuiman`: A Python client including API, GUI, and CLI for servers
   compliant with _OGC API - Processes_.
* `gavicore`: Common pydantic data models and utilities for the packages above.

## Installation

The `eozilla` package installs all components of Eozilla.

```commandline
pip install eozilla
```

However, your use case might require only a subset of Eozilla components.
Install just

- `procodile` if you develop processor applications,
- `appligator` if you deploy your processor applications,
- `wraptile` if you are an [OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes) service provider,
- `cuiman` if you need a client to operate with an [OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes) service.

The easiest way to test Eozilla is in a separate Python environment.
We use the [pixi](https://pixi.sh/) here, but you could do the same with
`pip`, `conda`, or `mamba`:

```bash
mkdir eozilla-test
cd eozilla-test

pixi init
pixi add python
pixi add --pypi eozilla
pixi shell

python -c "import eozilla; print(eozilla.__version__)"

cuiman --help
appligator --help
wraptile --help
```

We currently package Eozilla only as pip packages distributed via PyPI, but
we will publish `conda-forge` packages soon.

## Acknowledgements

Large parts of the work in the Eozilla project have been made possible by the
[ESA DTE-S2GOS project](https://dte-s2gos.rayference.eu/about/), where we cloudify a set of EO scene simulator
applications. The [ESA Sen4CAP project](https://www.esa-sen4cap.org/), where we
cloudify various Sentinel-based data processors, gave us the impulse to create
Eozilla as a set of reusable, standalone packages.
Hopefully Eozilla can support and will be supported by other future projects.
