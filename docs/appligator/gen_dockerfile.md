# Generating Dockerfiles

`appligator.airflow.gen_dockerfile.generate` assembles a Docker build
context and writes a `Dockerfile` for running workflow steps inside a
container orchestrator (e.g. Airflow's KubernetesPodOperator).

It does **not** invoke `docker build` — you control when and how the image
is built, which makes it easy to integrate into any CI pipeline.

---

## How it works

The function produces a two-stage image:

| Stage | Base image | Purpose |
|-------|-----------|---------|
| **build** | `ghcr.io/prefix-dev/pixi:<version>-bookworm-slim` | Resolves and installs the pixi environment |
| **runtime** | `debian:bookworm-slim` | Ships only the installed environment, not the source tree |

The pixi environment is copied from the build stage into the lean runtime
image, keeping the final image small and reproducible.

---

## Minimal example

Create a `build_docker_image.py` at the root of your pixi workspace (where
`pyproject.toml` and `pixi.lock` live) and run it with `pixi run python
build_docker_image.py`:

```python
from pathlib import Path
from appligator.airflow.gen_dockerfile import generate

generate(
    output_dir=Path("image"),
)
```

This writes `image/Dockerfile` and copies the necessary workspace files into
`image/`.  Build the image manually:

```bash
docker build -t myrepo/myimage:latest image/
```

---

## Non-editable local packages

In a monorepo where local packages are declared as pixi path-dependencies,
`pixi install` installs them in editable mode — meaning the runtime image
would need to carry the entire source tree.  Use `packages_dir` and
`local_packages` to convert them to non-editable installs instead, so only
the compiled environment is shipped:

```python
generate(
    output_dir=Path("image"),
    packages_dir=Path("packages"),               # directory with local packages
    local_packages=["my-utils", "my-app"],       # names inside packages_dir
)
```

`generate` will:

1. Copy only the listed packages into the build context.
2. Run `pixi install --locked` to resolve the full environment.
3. Run `pip install --no-deps --no-build-isolation` on each listed package to
   overwrite the editable install with a non-editable one.
4. **Not** copy `packages/` into the runtime stage — the source tree is no
   longer needed.

The pip binary path is derived from `workdir` and `pixi_env` automatically;
you never need to hardcode it.

---

## Adding extra packages at build time

Some packages are only needed inside the container (e.g. Airflow providers)
and should not pollute the local development environment.  Pass them via
`build_commands`, which runs before `pixi install`:

```python
generate(
    output_dir=Path("image"),
    build_commands=["RUN pixi add apache-airflow-providers-cncf-kubernetes"],
)
```

---

## Application-specific runtime steps

Use `runtime_commands` for any `COPY`, `RUN`, or `ENV` instructions that
belong to your application rather than the generic image:

```python
generate(
    output_dir=Path("image"),
    extra_files={"sensor_data": Path("data/sensor_data")},
    runtime_commands=[
        "COPY ./sensor_data /opt/pixi/sensor_data",
        "RUN myapp-cli prefetch-data",
        'RUN python -c "import myapp; print(\'myapp OK\')"',
    ],
)
```

`extra_files` copies host files into the build context so Docker can `COPY`
them.  The corresponding `COPY` instruction goes in `runtime_commands`.

---

## Full parameter reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `package_manager` | `str` | `"pixi"` | Package manager to use. Only `"pixi"` is currently supported. |
| `workdir` | `str` | `"/opt/pixi"` | `WORKDIR` in both stages. All env files and the entry point live here. |
| `output_dir` | `Path` | `Path("image")` | Directory where the build context is assembled. Recreated on every call. |
| `packages_dir` | `Path \| None` | `None` | Directory of local path-dependencies to copy into the build context. |
| `extra_files` | `dict[str, Path] \| None` | `None` | Extra files/dirs to add to the build context. Keys are names inside `output_dir`. |
| `build_commands` | `list[str] \| None` | `None` | Raw Dockerfile instructions inserted in the build stage **before** `pixi install`. |
| `local_packages` | `list[str] \| None` | `None` | Package names inside `packages_dir` to install as non-editable. Requires `packages_dir`. |
| `post_install_commands` | `list[str] \| None` | `None` | Raw Dockerfile instructions inserted in the build stage **after** `pixi install`. |
| `runtime_commands` | `list[str] \| None` | `None` | Raw Dockerfile instructions appended to the runtime stage before the `ENV` block. |
| `runtime_apt_packages` | `list[str] \| None` | `None` | Extra Debian packages to install at runtime (in addition to `libgomp1`). |
| `pixi_version` | `str` | `"0.50.2"` | Version tag of the `ghcr.io/prefix-dev/pixi` build image. |
| `pixi_env` | `str` | `"default"` | Name of the pixi environment to install and ship. |

---

## Out-of-context path dependencies

If your `pyproject.toml` contains path-dependencies that point outside the
build context (e.g. `{ path = "../eozilla/appligator", editable = true }` for
local development), `generate` strips them automatically before copying
`pyproject.toml` into the build context.  Dependencies pointing inside the
context (e.g. `packages/my-pkg`) are kept as-is.

This means you can safely use a `local-deps` pixi feature for development
without it breaking the Docker build.

---

## Entry point

Every generated image includes `run_step.py` (from `appligator.airflow`) as
its entry point.  It is invoked by the Airflow KubernetesPodOperator with a
JSON payload specifying the function to run and its inputs:

```
ENTRYPOINT ["python", "/opt/pixi/run_step.py"]
```
