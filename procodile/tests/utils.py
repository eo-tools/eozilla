import uuid
from pathlib import Path
from typing import Any

import xarray as xr

from procodile import ArtifactRef, ArtifactStore


class DummyArtifactStore(ArtifactStore):
    LOADER_NAME = "zarr_file"

    def __init__(
        self,
        store_kwargs: dict | None = None,
    ) -> None:
        if store_kwargs is None:
            store_kwargs = {}

        root = store_kwargs.get("root", ".artifacts")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        super().__init__()

    def is_big(self, obj: Any) -> bool:
        return isinstance(obj, xr.Dataset)

    def save(self, obj: Any) -> ArtifactRef:
        if not isinstance(obj, xr.Dataset):
            raise TypeError(f"Unsupported big object: {type(obj)}")

        data_id = f"{uuid.uuid4()}.zarr"
        path = self.root / data_id

        obj.to_zarr(path, mode="w")

        return ArtifactRef(path=str(path), loader=self.LOADER_NAME)

    def load(self, ref: ArtifactRef) -> xr.Dataset:
        if ref.loader != self.LOADER_NAME:
            raise ValueError(f"Unknown loader {ref.loader}")

        path = Path(ref.path)
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {path}")

        return xr.open_zarr(path)
