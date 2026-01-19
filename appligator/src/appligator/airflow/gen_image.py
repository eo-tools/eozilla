import importlib
import inspect
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
) -> str:
    if output_dir.exists():
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    import appligator.airflow.run_step as run_step

    shutil.copy(
        Path(run_step.__file__),
        output_dir / "run_step.py",
    )

    modules = set()
    for step in registry.steps.values():
        modules.add(step["step"].function.__module__)

    for module_name in modules:
        module = importlib.import_module(module_name)
        src = Path(inspect.getfile(module))
        shutil.copy(src, output_dir / src.name)

    dockerfile = output_dir / "Dockerfile"
    dockerfile.write_text(_render_dockerfile(use_local_packages))

    if use_local_packages:
        for pkg in EOZILLA_PACKAGES:
            src = Path.cwd() / pkg
            if src.exists():
                shutil.copytree(src, output_dir / pkg)

    subprocess.check_call(
        ["docker", "build", "-t", image_name, "."],
        cwd=output_dir,
    )

    return image_name


def _render_dockerfile(use_local_packages: bool) -> str:
    lines = [
        "FROM python:3.11-slim",
        "",
        "WORKDIR /app",
        "",
        "RUN pip install apache-airflow-providers-cncf-kubernetes xarray",
        "",
        "COPY . .",
        "RUN rm Dockerfile",
    ]

    if use_local_packages:
        for pkg in EOZILLA_PACKAGES:
            lines.append(f"COPY {pkg} /app/{pkg}")

        editable_paths = " ".join(f"/app/{pkg}" for pkg in EOZILLA_PACKAGES)
        lines.append(f"RUN pip install -e {editable_paths}")
    else:
        pkg_list = " ".join(EOZILLA_PACKAGES)
        lines.append(f"RUN pip install {pkg_list}")

    return "\n".join(lines) + "\n"
