#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import html
import json
import shutil
from pathlib import Path

import nbformat as nbf


def on_pre_build(config):
    """
    Runs the updates once before the build of the documentation

    References:
    - mkdocs hooks: https://www.mkdocs.org/user-guide/configuration/?#hooks
    - mkdocs events: https://www.mkdocs.org/dev-guide/plugins/#on_pre_build

    Args:
     - config: global MkDocsConfig Object
    """
    source = Path.cwd() / "notebooks"
    destination = Path.cwd() / "docs/notebooks"

    _update_files_in_docs(source, destination)
    print(f"[hooks] Updated notebooks: {source} to {destination}")

    for ipynb in destination.rglob("*.ipynb"):
        if _patch_notebook(ipynb):
            print(f"[hooks] Patched: {ipynb}")


def _patch_notebook(path: Path):
    """
    Changes the output type of Jupyter notebook cells from
    `json/application` to `text/html` to make the output readable
    in mkdocs documentation

    Args:
        - path: Path to notebooks in docs/

    Returns:
        - boolean indicator to report if notebook patching was done
    """
    nb = nbf.read(path, as_version=4)
    changed = False
    for cell in nb.cells:
        for out in cell.get("outputs", []):
            data = out.get("data", {})
            if isinstance(data, dict) and "application/json" in data:
                pretty = html.escape(
                    json.dumps(data["application/json"], indent=2, ensure_ascii=False)
                )
                data["text/html"] = (
                    f"<pre><code class='text-json'>{pretty}</code></pre>"
                )
                changed = True
    if changed:
        nbf.write(nb, path)
    return changed


def _update_files_in_docs(source: Path, destination: Path):
    """
    Adds notebooks to docs/notebooks

    Args:
        - source: Path to original notebooks
        - destination: Path to copy original notebooks to prepare for and add to
        mkdocs documentation
    """
    shutil.copytree(source, destination, dirs_exist_ok=True)
