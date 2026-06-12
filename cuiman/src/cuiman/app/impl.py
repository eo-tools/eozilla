#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from socket import socket
from typing import Any, Literal, TypeVar, Generic

from importlib.resources import files
from fastapi.staticfiles import StaticFiles
import remotestate as rs

from cuiman.app.display import (
    create_app_iframe,
    SerializedAppConfig,
    AppColorSchemeInput,
)
from gavicore.models import Output


T = TypeVar("T")

DIST_ENV_VAR = "EOZILLA_APP_DIST"


class ProcessIO(Generic[T]):
    def __init__(
        self,
        store: rs.Store,
        process_id: str,
        io_key: Literal["processesInputs", "processesOutputs"],
    ):
        self.store = store
        self.path = f"{io_key}.{process_id}"

    def __getattr__(self, key: str) -> T | None:
        return self.store.get(f"{self.path}.{key}")

    def __setattr__(self, key: str, value: T):
        self.store.set(f"{self.path}.{key}", value)

    def __getitem__(self, key: str) -> T | None:
        return self.store.get(f"{self.path}.{key}")

    def __setitem__(self, key: str, value: T) -> None:
        self.store.set(f"{self.path}.{key}", value)


class ProcessStore:
    def __init__(self, store: rs.Store, process_id: str):
        self.store = store
        self.process_id = process_id

    @property
    def inputs(self) -> ProcessIO[Any]:
        return ProcessIO(self.store, self.process_id, "processesInputs")

    @property
    def outputs(self) -> ProcessIO[Output | dict[str, Any]]:
        return ProcessIO(self.store, self.process_id, "processesOutputs")


class AppStore:
    def __init__(self):
        self.store = rs.Store(
            {
                "processesInputs": {},
                "processesOutputs": {},
            }
        )

    def __getitem__(self, process_id: str) -> ProcessStore:
        return ProcessStore(self.store, process_id)

    def __getattr__(self, process_id: str) -> ProcessStore:
        return ProcessStore(self.store, process_id)


def serve(
    app_store: AppStore | None = None,
    compact: bool = True,
    config: SerializedAppConfig | None = None,
    scheme: AppColorSchemeInput = "auto",
    width: str = "100%",
    height: int = 600,
):
    ui_dist = os.environ.get(DIST_ENV_VAR)
    app_url: str | None = None
    if ui_dist and ui_dist.startswith("http://") or ui_dist.startswith("https://"):
        app_url = ui_dist
    if not app_url:
        if ui_dist:
            static_path = ui_dist
        else:
            static_path = files("cuiman.app").joinpath("dist")
        ui_dist = StaticFiles(directory=str(static_path), html=True)
        port = _find_free_port()
        app_url = f"http://127.0.0.1:{port}"

    store = (app_store or AppStore()).store
    rs.serve(rs.Service(store), ui_dist=ui_dist, port=port)

    create_app_iframe(
        app_url,
        compact=compact,
        config=config,
        scheme=scheme,
        width=width,
        height=height,
    )


def _find_free_port() -> int:
    with socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
