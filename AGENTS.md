# Repository Guidance

This repository is a multi-package Python workspace for Eozilla.
Keep changes narrow, well-tested, and aligned with the existing Pixi-based
development workflow.

## Workspace Layout

- `appligator/`
- `cuiman/`
- `eozilla/`
- `gavicore/`
- `procodile/`
- `wraptile/`
- `eozilla-app/` (optional)
- `eozilla-airflow/`

## Preferred Commands

- Run project checks with `pixi run checks`.
- Run tests with `pixi run tests`.
- Run coverage with `pixi run coverage`.
- Format code with `pixi run format`.
- Build docs with `pixi run build-docs`.

If you only need a package-specific test run, prefer the matching `pytest`
target from `pyproject.toml`, for example:

- `pixi run test-cuiman`
- `pixi run test-gavicore`
- `pixi run test-procodile`
- `pixi run test-wraptile`

## Code Style

- Follow the repository's Black-style formatting.
- Keep imports grouped in standard-library, third-party, then first-party order.
- Prefer absolute first-party imports.
- Use `typing.TYPE_CHECKING` when it helps avoid circular imports.
- Add docstrings to public API classes, functions, constants, and type aliases.

## Testing Expectations

- Add or update tests for new behavior.
- Keep coverage close to 100% for touched code.
- When changing `cuiman`, check the relevant `cuiman/tests` coverage first.
- When changing shared models or utilities, check the relevant package tests.

## Safety And Review

- Do not use destructive git commands unless explicitly requested.
- Avoid overwriting user changes outside the current task scope.
- Prefer existing project tooling over ad hoc scripts.

