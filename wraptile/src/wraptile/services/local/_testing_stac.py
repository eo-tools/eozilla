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
        west, south = 10 + index * 1.25, 50
        products = run_dir / scene_id / "products"
        products.mkdir(parents=True)
        dataset = xr.Dataset(
            {
                "ndvi": (
                    ("lat", "lon"),
                    np.arange(4, dtype="float32").reshape(2, 2) + index,
                )
            },
            coords={
                "lat": [south + 0.25, south + 0.75],
                "lon": [west + 0.25, west + 0.75],
            },
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
        item = _item(scene_id, base, products, west, south, index)
        _write_preview(
            products / "preview.png", item["geometry"]["coordinates"][0], index
        )
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


def _footprint(west: float, south: float, index: int) -> list[list[float]]:
    """Return a closed, counterclockwise footprint resembling a clipped scene."""
    outlines = (
        ((0, 0.12), (0.18, 0), (0.84, 0.06), (1, 0.82), (0.78, 1), (0.06, 0.88)),
        ((0, 0.22), (0.26, 0), (0.93, 0.16), (1, 0.73), (0.68, 1), (0.12, 0.91)),
    )
    ring = [[west + x, south + y] for x, y in outlines[index % len(outlines)]]
    return ring + [ring[0].copy()]


def _write_preview(path: Path, ring: list[list[float]], index: int) -> None:
    """Draw deterministic, north-up illustrative vegetation and water scenery.

    This is independent of the tiny teaching grid, not satellite imagery or a
    scientific NDVI rendering. Transparent margins match the STAC footprint.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    size = 384
    rng = np.random.default_rng(2026 + index)
    terrain = np.zeros((size, size), dtype="float64")
    for resolution, weight in ((5, 0.5), (12, 0.25), (32, 0.15), (96, 0.1)):
        noise = (rng.random((resolution, resolution)) * 255).astype("uint8")
        with Image.fromarray(noise) as image:
            with image.resize((size, size), Image.Resampling.BICUBIC) as smooth:
                terrain += np.asarray(smooth) / 255 * weight

    y, x = np.mgrid[0:size, 0:size] / (size - 1)
    # Small agricultural parcels soften into forested hills at higher values.
    parcels = rng.uniform(0.12, 0.7, (24, 24))
    field_x = (0.94 * x + 0.34 * y + 0.015 * np.sin(15 * y)) % 1
    field_y = (0.94 * y - 0.34 * x + 0.015 * np.sin(12 * x)) % 1
    field = parcels[(field_y * 24).astype(int), (field_x * 24).astype(int)]
    forest = np.clip((terrain - 0.46) * 15, 0, 1)
    vegetation = np.clip((1 - forest) * field + forest * (0.65 + 0.35 * terrain), 0, 1)
    palette = np.array([[219, 208, 145], [168, 190, 104], [83, 139, 64], [26, 79, 43]])
    colours = np.stack(
        [
            np.interp(vegetation, [0, 0.35, 0.6, 1], palette[:, channel])
            for channel in range(3)
        ],
        axis=-1,
    )
    # A meandering river and a lake provide recognisable landscape structure.
    river_x = 0.48 + 0.13 * np.sin(8 * y + index) + 0.035 * np.sin(23 * y)
    lake_edge = 1 + 0.16 * np.sin(35 * x) * np.cos(42 * y)
    water = (abs(x - river_x) < 0.009) | (
        ((x - 0.64) / 0.10) ** 2 + ((y - 0.28) / 0.065) ** 2 < lake_edge
    )
    shade = 0.85 + 0.3 * terrain + rng.normal(0, 0.045, (size, size))
    colours = np.clip(colours * shade[..., None], 0, 255).astype("uint8")
    colours[water] = np.clip(
        np.array([55, 105, 125]) * shade[water, None], 0, 255
    ).astype("uint8")
    west, south = min(p[0] for p in ring), min(p[1] for p in ring)
    east, north = max(p[0] for p in ring), max(p[1] for p in ring)
    pixels = [
        (
            (lon - west) / (east - west) * (size - 1),
            (north - lat) / (north - south) * (size - 1),
        )
        for lon, lat in ring
    ]
    with Image.new("L", (size, size)) as mask:
        ImageDraw.Draw(mask).polygon(pixels, fill=255)
        with Image.fromarray(colours) as image:
            image.putalpha(mask)
            image.save(path)


def _item(
    scene_id: str, base: str, directory: Path, west: float, south: float, index: int
) -> dict[str, Any]:
    products = f"{scene_id}/products"
    return {
        "type": "Feature",
        "stac_version": "1.1.0",
        "stac_extensions": [
            "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json"
        ],
        "id": scene_id,
        "geometry": {
            "type": "Polygon",
            "coordinates": [_footprint(west, south, index)],
        },
        "bbox": [west, south, west + 1, south + 1],
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
                "alternate": {"local": {"href": (directory / "data.zarr").as_uri()}},
            },
            "preview": {
                "href": f"{products}/preview.png",
                "type": "image/png",
                "title": "Synthetic scene preview",
                "roles": ["thumbnail"],
                "alternate": {"local": {"href": (directory / "preview.png").as_uri()}},
            },
            "report": {
                "href": f"{products}/summary.csv",
                "type": "text/csv",
                "title": "Scene summary",
                "roles": ["metadata"],
            },
        },
    }
