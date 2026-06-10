#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Literal, TypeVar, Generic

import remotestate as rs
from gavicore.models import Output


T = TypeVar("T")


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


def serve(app_store: AppStore | None = None, iframe_height: int = 600):
    store = (app_store or AppStore()).store
    rs.serve(rs.Service(store), ui_dist="dist/app", iframe_height=iframe_height)
