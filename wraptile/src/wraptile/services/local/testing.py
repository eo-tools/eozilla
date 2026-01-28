#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import time
from pathlib import Path
from typing import Annotated, Optional

import pydantic
from pydantic import Field

from gavicore.models import InputDescription, Link, Schema
from procodile import FromMain, FromStep, JobContext, additional_parameters
from wraptile.services.local import LocalService

service = LocalService(
    title="Eozilla API Server (local dummy for testing)",
    description="Local test server implementing the OGC API - Processes 1.0 Standard",
)

registry = service.registry


@registry.main(
    id="sleep_a_while",
    title="Sleep Processor",
    description=(
        "Sleeps for `duration` seconds. "
        "Fails on purpose if `fail` is `True`. "
        "Returns the effective amount of sleep in seconds."
    ),
)
def sleep_a_while(
    duration: float = 10.0,
    fail: bool = False,
) -> float:
    ctx = JobContext.get()

    t0 = time.time()
    for i in range(101):
        ctx.report_progress(progress=i)
        if fail and i == 50:
            raise RuntimeError("Woke up too early")
        time.sleep(duration / 100)
    return time.time() - t0


@registry.main(
    id="primes_between",
    title="Prime Processor",
    description=(
        "Returns the list of prime numbers between a `min_val` and `max_val`."
    ),
)
def primes_between(
    min_val: int = pydantic.Field(0, ge=0),
    max_val: int = pydantic.Field(100, le=100),
) -> list[int]:
    ctx = JobContext.get()

    if max_val < 2 or max_val <= min_val:
        raise ValueError("max_val must be greater 1 and greater min_val")

    ctx.report_progress(message="Step 1: Generate sieve up to sqrt(max_val)")
    limit = int(max_val**0.5) + 1
    is_prime_small = [True] * (limit + 1)
    is_prime_small[0:2] = [False, False]
    for i in range(2, int(limit**0.5) + 1):
        if is_prime_small[i]:
            for j in range(i * i, limit + 1, i):
                is_prime_small[j] = False
    small_primes = [i for i, prime in enumerate(is_prime_small) if prime]

    ctx.report_progress(
        message="Step 2: Create the sieve for the range [min_val, max_val]"
    )
    sieve_range = max_val - min_val + 1
    is_prime = [True] * sieve_range

    for p in small_primes:
        # Find the first multiple of p in the range [min_val, max_val]
        start = max(p * p, ((min_val + p - 1) // p) * p)
        for j in range(start, max_val + 1, p):
            is_prime[j - min_val] = False

    for n in range(min_val, min(min_val + 2, max_val + 1)):
        if n < 2:
            is_prime[n - min_val] = False

    ctx.report_progress(message="Done")
    return [min_val + i for i, prime in enumerate(is_prime) if prime]


# noinspection PyArgumentList
@registry.main(
    id="simulate_scene",
    title="Generate scene for testing",
    description=(
        "Simulate a set scene images slices for testing. "
        "Creates an xarray dataset with `periodicity` time slices "
        "and writes it as Zarr into a temporary location. "
        "Requires installed `dask`, `xarray`, and `zarr` packages."
    ),
    inputs={
        "var_names": InputDescription(
            title="Variable names",
            description="Comma-separated list of variable names.",
            additionalParameters=additional_parameters({"level": "advanced"}),
            schema=Schema(),  # type: ignore[call-arg]
        ),
        "bbox": Field(
            title="Bounding box",
            description="Bounding box in geographical coordinates.",
            json_schema_extra=dict(format="bbox"),
        ),
        "resolution": Field(
            title="Spatial resolution",
            description="Spatial resolution in degree.",
            ge=0.01,
            le=1.0,
        ),
        "start_date": Field(
            title="Start date",
            json_schema_extra=dict(format="date"),
        ),
        "end_date": Field(
            title="End date",
            json_schema_extra=dict(format="date"),
        ),
        "periodicity": Field(
            title="Periodicity",
            description="Size of time steps in days.",
            ge=1,
            le=10,
        ),
        "output_path": InputDescription(
            title="Output path",
            description="Local output path or URI.",
            additionalParameters=additional_parameters({"level": "advanced"}),
            schema=Schema(minLength=1),  # type: ignore[call-arg]
        ),
    },
)
def simulate_scene(
    var_names: str = "a, b, c",
    bbox: tuple[float, float, float, float] = (-180, -90, 180, 90),
    resolution: float = 0.5,
    start_date: str = "2025-01-01",
    end_date: str = "2025-02-01",
    periodicity: int = 1,
    output_path: Optional[str] = None,
) -> Link:
    # dependencies only required for this operation
    import dask.array as da
    import numpy as np
    import xarray as xr

    # print(
    #     dict(
    #         var_names=var_names,
    #         bbox=bbox,
    #         resolution=resolution,
    #         start_date=start_date,
    #         end_date=end_date,
    #         periodicity=periodicity,
    #     )
    # )

    var_names_: list[str] = [name.strip() for name in var_names.split(",")]
    start_date_: datetime.date = datetime.date.fromisoformat(start_date)
    end_date_: datetime.date = datetime.date.fromisoformat(end_date)

    x1, y1, x2, y2 = bbox
    x_size = round((x2 - x1) / resolution)
    y_size = round((y2 - y1) / resolution)
    time_size = round((end_date_ - start_date_).days / periodicity)
    r05 = resolution / 2

    dataset = xr.Dataset()
    dataset.coords["lon"] = xr.DataArray(
        np.linspace(x1 + r05, x2 - r05, x_size), dims="lon"
    )
    dataset.coords["lat"] = xr.DataArray(
        np.linspace(y1 + r05, y2 - r05, y_size), dims="lat"
    )
    dataset.coords["time"] = xr.DataArray(
        np.array(
            [start_date_ + datetime.timedelta(days=days) for days in range(time_size)],
            dtype=np.datetime64,
        ),
        dims="time",
    )
    for var_name in var_names_:
        dataset[var_name] = xr.DataArray(
            da.zeros(shape=(time_size, y_size, x_size)), dims=("time", "lat", "lon")
        )

    if not output_path:
        output_path = "memory://datacube.zarr"

    dataset.to_zarr(output_path, mode="w", zarr_format=2)
    if "://" in output_path:
        href = output_path
    else:
        href = Path(output_path).resolve().as_uri()
    # noinspection PyArgumentList
    return Link(href=href, hreflang=None, type="application/zarr", rel=None)


class SceneSpec(pydantic.BaseModel):
    threshold: float
    factor: float
    # TODO: uncomment and see tests fail!
    # bbox: Optional[Bbox] = None


@registry.main(
    id="return_base_model",
    title="BaseModel Test",
)
def return_base_model(
    scene_spec: SceneSpec,
) -> SceneSpec:
    return scene_spec


@registry.main(
    id="process_pipeline",
    inputs={"id": Field(title="main input")},
    outputs={
        "a": Field(title="main result", description="The result of the main step"),
    },
    description=(
        "This is a workflow with several steps and defined dependencies that "
        "execute sequentially."
    ),
    title="A Big Workflow",
)
def process_pipeline(id: str) -> str:
    print("Initializing process pipeline")
    return id


@process_pipeline.step(
    id="read_data",
    inputs={"id": FromMain(output="a")},
)
def read_data(id: str) -> str:
    print("Reading data")
    return id + "_read"


@process_pipeline.step(
    id="preprocess_data",
)
def preprocess_data(
    id: Annotated[str, FromStep(step_id="read_data", output="return_value")],
) -> Annotated[str, {"preprocessed": Field(title="Preprocessed dataset")}]:
    print("Preprocessing data")
    return id + "_preprocessed"


@process_pipeline.step(
    id="feature_engineering",
    outputs={
        "some_str": Field(title="Some Str"),
    },
)
def feature_engineering(
    id: Annotated[str, FromStep(step_id="preprocess_data", output="preprocessed")],
) -> str:
    print("Performing feature engineering")
    return id + "_feature_mean"


@process_pipeline.step(
    id="resample_data",
    inputs={"id2": FromMain(output="a")},
    outputs={
        "some_other_str": Field(title="Some other Str"),
    },
)
def resample_data(
    id: Annotated[str, FromStep(step_id="feature_engineering", output="some_str")],
    id2: str,
) -> tuple[str, str]:
    print("Resampling data")
    return id, f"resampled_from={id2}"


@process_pipeline.step(
    id="store_data",
    outputs={
        "final": Field(title="Final output"),
    },
)
def store_data(
    id: Annotated[
        tuple[str, str],
        FromStep(step_id="resample_data", output="some_other_str"),
    ],
    second_input: Annotated[
        str, FromStep(step_id="feature_engineering", output="some_str")
    ],
) -> tuple[tuple[str, str], str]:
    print("Storing data")
    return id, second_input
