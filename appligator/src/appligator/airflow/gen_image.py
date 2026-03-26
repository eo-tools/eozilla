#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import importlib
import inspect
import re
import shutil
import subprocess
from pathlib import Path

from procodile import WorkflowStepRegistry

EOZILLA_PACKAGES = ("procodile", "wraptile", "gavicore", "appligator")


def gen_image(
    registry: WorkflowStepRegistry,
    *,
    image_name: str,
    use_local_packages: bool = False,
    output_dir: Path = Path("image"),
    pixi_version: str = "0.50.2",
    extra_files: dict[str, Path] | None = None,
    dockerfile_extra: str | None = None,
    runtime_apt_packages: list[str] | None = None,
    build_stage_extra: str | None = None,
) -> str:
    """
    Generate a Docker image for running workflow steps in container orchestrator.

    Produces a multi-stage pixi-based image:
      - Stage 1 (build): resolves and installs the pixi environment from the
        workspace ``pyproject.toml`` / ``pixi.lock`` found in the current
        working directory.
      - Stage 2 (runtime): ``debian:bookworm-slim`` with the pixi env copied
        in, keeping the final image small and reproducible.

    The working directory must contain a ``pyproject.toml`` and ``pixi.lock``
    that describe the full runtime environment.  If a ``packages/`` subdirectory
    exists it is included in the build context so pixi can resolve local
    path-dependencies declared in ``pyproject.toml``.

    Args:
        registry: Registry of workflow steps whose modules will be copied into
            the image.
        image_name: Docker image tag (e.g. ``"myrepo/myimage:latest"``).
        use_local_packages: When ``True``, copies the local eozilla sub-packages
            (procodile, wraptile, gavicore, appligator) from the current working
            directory into the build context.  Useful during development when
            those packages have not yet been published.
        output_dir: Directory where the build context is assembled before
            ``docker build`` is invoked.  Recreated from scratch on every call.
        pixi_version: Version tag of the ``ghcr.io/prefix-dev/pixi`` build
            image, e.g. ``"0.50.2"``.
        extra_files: Additional files or directories to include in the build
            context.  Keys are the names they will have inside ``output_dir``
            (and therefore inside the Docker build context); values are the
            source paths on the host.  Use ``dockerfile_extra`` to write the
            corresponding ``COPY`` (and any other) instructions.

            Example for an application that ships a data directory::

                gen_image(
                    registry,
                    image_name="myrepo/myapp:latest",
                    extra_files={"sensor_data": Path("data")},
                    dockerfile_extra=dedent(\"\"\"
                        COPY ./sensor_data /opt/pixi/sensor_data
                        RUN myapp-cli prefetch-data
                        RUN python -c "import myapp; print('myapp OK')"
                    \"\"\"),
                )

        dockerfile_extra: Raw Dockerfile instructions appended to the runtime
            stage, immediately before the ``ENTRYPOINT``.  Use this for
            application-specific ``COPY``, ``RUN``, and ``ENV`` lines that do
            not belong in the generic image builder.
        build_stage_extra: Raw Dockerfile instructions inserted into the build
            stage, immediately before ``RUN pixi install --locked``.  Use this
            for commands that must modify the pixi environment prior to
            installation, e.g. ``RUN pixi add some-package``.
        runtime_apt_packages: Extra Debian packages to install in the runtime
            stage (in addition to the always-present ``libgomp1``).

    Returns:
        The image name that was built.
    """

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── run_step.py ───────────────────────────────────────────────────────────
    import appligator.airflow.run_step as run_step_module

    shutil.copy(Path(run_step_module.__file__), output_dir / "run_step.py")

    # ── step module source files ──────────────────────────────────────────────
    step_module_filenames: list[str] = []
    modules: set[str] = set()
    for step in registry.steps.values():
        modules.add(step["step"].function.__module__)

    for module_name in modules:
        module = importlib.import_module(module_name)
        src = Path(inspect.getfile(module))
        shutil.copy(src, output_dir / src.name)
        step_module_filenames.append(src.name)

    # ── pixi workspace files ──────────────────────────────────────────────────
    for filename in ("pyproject.toml", "pixi.lock"):
        src = Path.cwd() / filename
        if not src.exists():
            raise FileNotFoundError(
                f"{filename} not found in the current directory ({Path.cwd()})."
                " gen_image must be called from the pixi workspace root."
            )
        shutil.copy(src, output_dir / filename)

    # ── packages/ directory (local pixi path-dependencies) ───────────────────
    packages_src = Path.cwd() / "packages"
    has_packages_dir = packages_src.exists() and packages_src.is_dir()
    if has_packages_dir:
        shutil.copytree(packages_src, output_dir / "packages")

    # ── local eozilla packages (development mode) ─────────────────────────────
    if use_local_packages:
        for pkg in EOZILLA_PACKAGES:
            src = Path.cwd() / pkg
            if src.exists():
                shutil.copytree(src, output_dir / pkg)

    # ── application-specific extra files ─────────────────────────────────────
    for dest_name, src_path in (extra_files or {}).items():
        if not src_path.exists():
            raise FileNotFoundError(
                f"extra_files entry {dest_name!r}: source path not found: {src_path}"
            )
        dest = output_dir / dest_name
        if src_path.is_dir():
            shutil.copytree(src_path, dest)
        else:
            shutil.copy2(src_path, dest)

    # ── Dockerfile ────────────────────────────────────────────────────────────
    dockerfile = output_dir / "Dockerfile"
    dockerfile.write_text(
        _render_dockerfile(
            use_local_packages=use_local_packages,
            has_packages_dir=has_packages_dir,
            pixi_version=pixi_version,
            runtime_apt_packages=runtime_apt_packages,
            step_module_filenames=step_module_filenames,
            dockerfile_extra=dockerfile_extra,
            build_stage_extra=build_stage_extra,
        )
    )

    # ── validate & build ──────────────────────────────────────────────────────
    if not re.fullmatch(r"[a-zA-Z0-9._/-]+(?::[a-zA-Z0-9._-]+)?", image_name):
        raise ValueError(f"Invalid image name: {image_name!r}")

    docker_path = shutil.which("docker")
    if docker_path is None:
        raise RuntimeError("docker executable not found on PATH")

    subprocess.check_call(  # noqa: S603
        [docker_path, "build", "-t", image_name, "."],
        cwd=output_dir,
        shell=False,
    )

    return image_name


def _render_dockerfile(
    *,
    use_local_packages: bool,
    has_packages_dir: bool,
    pixi_version: str,
    runtime_apt_packages: list[str] | None,
    step_module_filenames: list[str],
    dockerfile_extra: str | None,
    build_stage_extra: str | None,
) -> str:
    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# Generated by appligator — do not edit by hand.",
        "# To regenerate, call appligator.airflow.gen_image.gen_image().",
        "",
    ]

    # ── Stage 1: build ────────────────────────────────────────────────────────
    lines += [
        "# ── Stage 1: build ────────────────────────────────────────────────",
        f"FROM ghcr.io/prefix-dev/pixi:{pixi_version}-bookworm-slim AS build",
        "",
        "RUN apt-get update \\",
        " && apt-get install -y --no-install-recommends git ca-certificates \\",
        " && update-ca-certificates \\",
        " && rm -rf /var/lib/apt/lists/*",
        "",
        "WORKDIR /opt/pixi",
        "",
        "COPY ./pyproject.toml ./pyproject.toml",
        "COPY ./pixi.lock      ./pixi.lock",
    ]

    if has_packages_dir:
        lines.append("COPY ./packages       ./packages")

    if use_local_packages:
        for pkg in EOZILLA_PACKAGES:
            lines.append(f"COPY ./{pkg:<12} ./{pkg}")

    if build_stage_extra:
        lines += [
            "",
            build_stage_extra.rstrip(),
        ]

    lines += [
        "",
        "RUN pixi install --locked -e default",
    ]

    # ── Stage 2: runtime ──────────────────────────────────────────────────────
    lines += [
        "",
        "# ── Stage 2: runtime ──────────────────────────────────────────────",
        "FROM debian:bookworm-slim",
        "WORKDIR /opt/pixi",
        "",
    ]

    runtime_pkgs = ["libgomp1"] + (runtime_apt_packages or [])
    pkg_lines = " \\\n    ".join(runtime_pkgs)
    lines += [
        "RUN apt-get update && apt-get install -y --no-install-recommends \\",
        f"    {pkg_lines} \\",
        "    && rm -rf /var/lib/apt/lists/*",
        "",
        "COPY --from=build /opt/pixi/.pixi/envs/default /opt/pixi/.pixi/envs/default",
    ]

    if has_packages_dir:
        lines.append(
            "COPY --from=build /opt/pixi/packages           /opt/pixi/packages"
        )

    if use_local_packages:
        for pkg in EOZILLA_PACKAGES:
            lines.append(f"COPY --from=build /opt/pixi/{pkg:<12} /opt/pixi/{pkg}")

    lines += [
        "COPY --from=build /opt/pixi/pyproject.toml     /opt/pixi/pyproject.toml",
        "COPY --from=build /opt/pixi/pixi.lock          /opt/pixi/pixi.lock",
        "",
        "COPY ./run_step.py /opt/pixi/run_step.py",
    ]

    for filename in step_module_filenames:
        lines.append(f"COPY ./{filename} /opt/pixi/{filename}")

    lines += [
        "",
        'ENV PIXI_ENV="/opt/pixi/.pixi/envs/default"',
        'ENV PIXI_PROJECT_ROOT="/opt/pixi"',
        'ENV PATH="$PIXI_ENV/bin:$PATH"',
        'ENV LD_LIBRARY_PATH="$PIXI_ENV/lib:$LD_LIBRARY_PATH"',
        'ENV PROJ_DATA="$PIXI_ENV/share/proj"',
        'ENV XDG_CACHE_HOME="/opt/pixi/cache"',
    ]

    if dockerfile_extra:
        lines += [
            "",
            dockerfile_extra.rstrip(),
        ]

    lines += [
        "",
        'ENTRYPOINT ["python", "/opt/pixi/run_step.py"]',
    ]

    return "\n".join(lines) + "\n"
