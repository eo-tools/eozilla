#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from typing import Any

import tomlkit

# List of workspaces to update
workspace_names = [
    "appligator",
    "cuiman",
    "eozilla",
    "gavicore",
    "procodile",
    "wraptile",
]


def main():
    # Get version from root pyproject.toml
    root_path = Path("pyproject.toml")
    root_data: dict[str, Any] = tomlkit.parse(root_path.read_text())
    try:
        root_version = root_data["project"]["version"]
    except KeyError:
        raise RuntimeError("version not found in [project]")

    # Update each subproject's pyproject.toml
    for name in workspace_names:
        workspace_path = Path(name) / "pyproject.toml"
        if not workspace_path.exists():
            print(f"⚠️  Skipping {workspace_path} — no pyproject.toml")
            continue
        print(f"🔧 Updating {name}/pyproject.toml")
        workspace_data = tomlkit.parse(workspace_path.read_text())
        project: dict[str, Any] = workspace_data["project"]
        project_version: str | None = project.get("version")
        project_dependencies: list[str] = project.get("dependencies") or []
        changed = False
        for i, dep in enumerate(project_dependencies):
            for name_ in workspace_names:
                if dep.startswith(f"{name_}"):
                    dep_update = f"{name_} >={root_version}"
                    if dep != dep_update:
                        project_dependencies[i] = dep_update
                        changed = True
        if project_version != root_version:
            project["version"] = root_version
            changed = True
        if changed:
            workspace_path.write_text(tomlkit.dumps(workspace_data))
            print(f"✅ Synced version {root_version} in {workspace_path}")
        else:
            print(f"✅ Version {root_version} in {workspace_path} already up-to-date.")


if __name__ == "__main__":
    main()
