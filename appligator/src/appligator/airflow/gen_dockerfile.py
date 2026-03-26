#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import shutil
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-retyped-def]

from jinja2 import Environment, PackageLoader

_SUPPORTED_PACKAGE_MANAGERS = ("pixi",)


def generate(
    *,
    package_manager: str = "pixi",
    workdir: str = "/opt/pixi",
    output_dir: Path = Path("image"),
    packages_dir: Path | None = None,
    extra_files: dict[str, Path] | None = None,
    build_commands: list[str] | None = None,
    local_packages: list[str] | None = None,
    post_install_commands: list[str] | None = None,
    runtime_commands: list[str] | None = None,
    runtime_apt_packages: list[str] | None = None,
    pixi_version: str = "0.50.2",
    pixi_env: str = "default",
) -> Path:
    """
    Generate a Dockerfile and assemble a build context directory.

    Produces a multi-stage image using the chosen package manager.  The build
    context is written to ``output_dir``; the generated ``Dockerfile`` path is
    returned.

    The working directory must contain the package-manager workspace files
    (``pyproject.toml`` + ``pixi.lock`` for pixi).  If a ``packages/``
    subdirectory exists it is included so the package manager can resolve
    local path-dependencies.

    Args:
        package_manager: Package manager to use.  Currently only ``"pixi"``
            is supported.
        workdir: Absolute path used as ``WORKDIR`` in both build and runtime
            stages.  All environment files and the entry point are placed
            under this path inside the image.  Defaults to ``/opt/pixi``.
        output_dir: Directory where the build context is assembled.  Recreated
            from scratch on every call.
        packages_dir: Path to the directory containing local path-dependencies
            that the package manager needs to resolve (e.g. ``packages/`` in a
            monorepo).  When provided, the directory is copied into the build
            context.  Defaults to ``None`` (no local packages directory).
        extra_files: Additional files or directories to copy into the build
            context.  Keys are the names they will have inside ``output_dir``
            (and therefore inside the Docker build context); values are the
            source paths on the host.  Write the corresponding ``COPY``
            instructions via ``runtime_commands`` or ``build_commands``.
        build_commands: Raw Dockerfile instructions inserted into the *build*
            stage, immediately *before* the package-manager install step.
            Typical use: ``["RUN pixi add some-extra-package"]``.
        local_packages: Paths to local packages (relative to the build
            context root) that should be installed as non-editable after the
            package-manager install step.  This overwrites the editable
            installs created by ``pixi install`` so the source tree does not
            need to be shipped in the runtime image.  The pip binary path is
            derived from ``workdir`` and ``pixi_env`` automatically::

                local_packages=["s2gos-utils", "s2gos-apps"]

            The generated ``RUN`` command is prepended to
            ``post_install_commands``.
        post_install_commands: Raw Dockerfile instructions inserted into the
            *build* stage, immediately *after* the package-manager install
            step.  Use this for any further build-stage post-processing beyond
            what ``local_packages`` handles.

        runtime_commands: Raw Dockerfile instructions appended to the *runtime*
            stage, after the standard ``COPY`` block and before the ``ENV``
            block.  May include any valid Dockerfile directive (``COPY``,
            ``RUN``, ``ENV``, comments, …).
        runtime_apt_packages: Extra Debian packages to install in the runtime
            stage in addition to the always-present ``libgomp1``.
        pixi_version: Version tag of the ``ghcr.io/prefix-dev/pixi`` build
            image (pixi package manager only).
        pixi_env: Name of the pixi environment to install and ship.
            Defaults to ``"default"``.

    Returns:
        Path to the generated ``Dockerfile`` inside ``output_dir``.

    Raises:
        ValueError: If ``package_manager`` is not supported.
        FileNotFoundError: If required workspace files are missing or an
            ``extra_files`` source path does not exist.
    """
    if package_manager not in _SUPPORTED_PACKAGE_MANAGERS:
        raise ValueError(
            f"Unsupported package manager {package_manager!r}. "
            f"Supported: {_SUPPORTED_PACKAGE_MANAGERS}"
        )

    if local_packages and packages_dir is None:
        raise ValueError(
            "local_packages requires packages_dir to be set so the source tree "
            "is copied into the build context before pip can install from it."
        )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── run_step.py ───────────────────────────────────────────────────────────
    import appligator.airflow.run_step as run_step_module

    shutil.copy(Path(run_step_module.__file__), output_dir / "run_step.py")

    # ── workspace files ───────────────────────────────────────────────────────
    _copy_workspace_files(output_dir, package_manager)

    # ── packages directory ────────────────────────────────────────────────────
    has_packages_dir = packages_dir is not None and packages_dir.is_dir()
    if has_packages_dir:
        assert packages_dir is not None  # narrowing for type checker
        packages_to_copy = local_packages or []
        for pkg in packages_to_copy:
            src = packages_dir / pkg
            if not src.exists():
                raise FileNotFoundError(
                    f"local_packages entry {pkg!r} not found in {packages_dir}"
                )
            shutil.copytree(src, output_dir / packages_dir.name / pkg)

    # ── extra files ───────────────────────────────────────────────────────────
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

    # ── non-editable local package installs ──────────────────────────────────
    resolved_post_install = list(post_install_commands or [])
    if local_packages:
        assert packages_dir is not None  # narrowing for type checker; enforced by validation above
        pip = f"{workdir}/.pixi/envs/{pixi_env}/bin/pip"
        pkgs = " \\\n    ".join(
            f"./{packages_dir.name}/{pkg}" for pkg in local_packages
        )
        resolved_post_install.insert(
            0,
            f"RUN {pip} install --no-deps --no-build-isolation \\\n    {pkgs}",
        )

    # ── Dockerfile ────────────────────────────────────────────────────────────
    env = Environment(
        loader=PackageLoader("appligator.airflow", "templates"),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701 — Dockerfile output, not HTML
    )
    template = env.get_template(f"{package_manager}.Dockerfile.j2")
    content = template.render(
        pixi_version=pixi_version,
        pixi_env=pixi_env,
        workdir=workdir,
        packages_dirname=packages_dir.name if packages_dir else None,
        has_packages_dir=has_packages_dir,
        build_commands=build_commands or [],
        post_install_commands=resolved_post_install,
        runtime_commands=runtime_commands or [],
        all_apt_packages=["libgomp1"] + (runtime_apt_packages or []),
    )

    dockerfile = output_dir / "Dockerfile"
    dockerfile.write_text(content)
    return dockerfile


def _copy_workspace_files(output_dir: Path, package_manager: str) -> None:
    """Copy package-manager workspace files into the build context."""
    if package_manager == "pixi":
        for filename in ("pyproject.toml", "pixi.lock"):
            src = Path.cwd() / filename
            if not src.exists():
                raise FileNotFoundError(
                    f"{filename} not found in the current directory ({Path.cwd()})."
                    f" gen_dockerfile must be called from the {package_manager} workspace root."
                )
            if filename == "pyproject.toml":
                _copy_pyproject_toml_stripped(src, output_dir / filename)
            else:
                shutil.copy(src, output_dir / filename)


def _copy_pyproject_toml_stripped(src: Path, dest: Path) -> None:
    """Copy pyproject.toml, removing pypi path-deps that point outside the build context.

    Dependencies like ``{ path = "../eozilla/appligator", editable = true }``
    reference sibling directories that do not exist inside the Docker build
    context.  Leaving them in causes ``pixi add`` / ``pixi install`` to fail
    when run inside the container.  We strip any pypi dependency whose path
    starts with ``..`` or is absolute; local ``packages/`` subdirectory deps
    (relative paths that don't escape the context) are kept as-is.
    """
    import tomli_w

    data = tomllib.loads(src.read_text())

    def _strip_out_of_context(pypi_deps: dict) -> dict:
        return {
            name: spec
            for name, spec in pypi_deps.items()
            if not (
                isinstance(spec, dict)
                and "path" in spec
                and (Path(spec["path"]).is_absolute() or spec["path"].startswith(".."))
            )
        }

    if "pypi-dependencies" in data.get("tool", {}).get("pixi", {}):
        data["tool"]["pixi"]["pypi-dependencies"] = _strip_out_of_context(
            data["tool"]["pixi"]["pypi-dependencies"]
        )

    for feature in data.get("tool", {}).get("pixi", {}).get("feature", {}).values():
        if "pypi-dependencies" in feature:
            feature["pypi-dependencies"] = _strip_out_of_context(
                feature["pypi-dependencies"]
            )

    dest.write_bytes(tomli_w.dumps(data).encode())
