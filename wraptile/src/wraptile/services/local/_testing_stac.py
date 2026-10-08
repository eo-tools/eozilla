# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License.

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from gavicore.models import Link


def output_settings() -> tuple[Path, str]:
    """Return the testing artifact directory and its advertised HTTP base."""
    directory = Path(os.environ.get("EOZILLA_TESTING_STAC_DIR", ".pixi/testing-stac"))
    base = os.environ.get(
        "EOZILLA_TESTING_STAC_URL", "http://localhost:8008/testing-stac"
    )
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Testing STAC base must be an absolute HTTP URL without credentials"
        )
    return directory.resolve(), base.rstrip("/")


def mount_artifacts(app: FastAPI) -> None:
    """Mount only the configured testing artifact directory, without enumeration."""
    directory, _ = output_settings()
    directory.mkdir(parents=True, exist_ok=True)
    app.routes[:] = [
        route for route in app.routes if getattr(route, "name", None) != "testing-stac"
    ]
    app.mount("/testing-stac", StaticFiles(directory=directory), name="testing-stac")


def create_outputs(item_count: int, inline: bool) -> tuple[Any, Any, Link, int, None]:
    """Generate small owned products and equivalent inline/linked STAC outputs."""
    import numpy as np
    import xarray as xr

    directory, public_base = output_settings()
    run_id = uuid4().hex
    run_dir = directory / run_id
    run_dir.mkdir(parents=True)
    base = f"{public_base}/{run_id}"
    items = []
    for index in range(item_count):
        scene_id = f"scene-{index + 1}"
        products = run_dir / scene_id / "products"
        products.mkdir(parents=True)
        dataset = xr.Dataset(
            {
                "ndvi": (
                    ("lat", "lon"),
                    np.arange(4, dtype="float32").reshape(2, 2) + index,
                )
            },
            coords={"lat": [50.25, 50.75], "lon": [10.25, 10.75]},
        )
        try:
            dataset.to_zarr(str(products / "data.zarr"), mode="w", zarr_format=2)
        finally:
            dataset.close()
        (products / "summary.csv").write_text(
            f"scene,mean_ndvi\n{scene_id},{1.5 + index}\n",
            encoding="utf-8",
            newline="\n",
        )
        item = _item(scene_id, base)
        items.append(item)
        _write_json(run_dir / f"{scene_id}.json", item)
    collection = {
        "type": "FeatureCollection",
        "features": deepcopy(items),
        "links": [
            {
                "rel": "self",
                "href": f"{base}/items.json",
                "type": "application/geo+json",
            }
        ],
        "testing:complete": True,
    }
    _write_json(run_dir / "items.json", collection)
    report = Link(href=f"{base}/scene-1/products/summary.csv", type="text/csv")
    if inline:
        return items[0], collection, report, item_count, None
    return (
        Link(href=f"{base}/scene-1.json", type="application/geo+json"),
        Link(href=f"{base}/items.json", type="application/geo+json"),
        report,
        item_count,
        None,
    )


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def _item(scene_id: str, base: str) -> dict[str, Any]:
    products = f"{scene_id}/products"
    return {
        "type": "Feature",
        "stac_version": "1.1.0",
        "stac_extensions": [],
        "id": scene_id,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[10, 50], [11, 50], [11, 51], [10, 51], [10, 50]]],
        },
        "bbox": [10, 50, 11, 51],
        "properties": {"datetime": "2026-01-01T00:00:00Z", "testing:scene": scene_id},
        "links": [
            {
                "rel": "self",
                "href": f"{base}/{scene_id}.json",
                "type": "application/geo+json",
            }
        ],
        "assets": {
            "data": {
                "href": f"{products}/data.zarr",
                "type": "application/zarr",
                "title": "NDVI grid",
                "roles": ["data"],
            },
            "report": {
                "href": f"{products}/summary.csv",
                "type": "text/csv",
                "title": "Scene summary",
                "roles": ["metadata"],
            },
            "products": {
                "href": products,
                "type": "inode/directory",
                "title": "Declared products folder",
                "roles": ["data"],
            },
        },
    }
