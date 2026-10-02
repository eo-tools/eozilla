[![CI](https://github.com/eo-tools/eozilla/actions/workflows/ci.yml/badge.svg)](https://github.com/eo-tools/eozilla/actions/workflows/ci.yml)
[![Codecov](https://codecov.io/gh/eo-tools/eozilla/graph/badge.svg?token=T3EXHBMD0G)](https://codecov.io/gh/eo-tools/eozilla)
[![Pixi](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![License](https://img.shields.io/github/license/eo-tools/eozilla)](https://github.com/eo-tools/eozilla)

# Eozilla Gavicore

Pydantic data models and common utilities for other Eozilla packages

Models and service interfaces follow the OGC API - Processes specification parts:

- `gavicore.models.core` and `gavicore.service.core`: Part 1, Core.
- `gavicore.models.dru` and `gavicore.service.dru`: Part 2, Deploy, Replace,
  Undeploy (DRU).
- `gavicore.service.errors`: shared API error helpers.

Import models and interfaces directly from their `core` or `dru` modules.
Tests mirror the source structure under `tests/models/` and `tests/service/`.
See the [documentation](https://eo-tools.github.io/eozilla/gavicore/)
for details and the [changelog](https://github.com/eo-tools/eozilla/blob/main/CHANGES.md)
for release notes.

