import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Union

import xarray as xr
from xcube.core.store import new_data_store

BigObject = Union[xr.Dataset]

NormalizedOutputs = dict[str, Any]


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    loader: str


class ArtifactStore:
    def __init__(
        self, store_id: str = "file", store_kwargs: dict | None = None
    ) -> None:
        if not store_kwargs:
            store_kwargs = {}
        if store_id == "file" and "root" not in store_kwargs:
            store_kwargs.update({"root": ".artifacts", "max_depth": 5})
        self.store = new_data_store(store_id, **store_kwargs)

    def is_big(self, obj: Any) -> bool:
        return isinstance(obj, xr.Dataset)

    def save(self, obj: BigObject) -> ArtifactRef:
        if isinstance(obj, xr.Dataset):
            data_id = str(uuid.uuid4()) + ".zarr"
            self.store.write_data(obj, data_id)
            return ArtifactRef(data_id, "xcube_file_store")

        raise TypeError(f"Unsupported big object: {type(obj)}")

    def load(self, ref: ArtifactRef) -> Any:
        if ref.loader == "xcube_file_store":
            return self.store.open_data(ref.path)
        raise ValueError(f"Unknown loader {ref.loader}")


class ExecutionContext:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store
        self.main: dict[str, Any] = {}
        self.steps: dict[str, dict[str, Any]] = {}

    def resolve(self, value: Any) -> Any:
        """Recursively resolve the inputs."""
        if isinstance(value, ArtifactRef):
            return self.store.load(value)

        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}

        if isinstance(value, tuple):
            return tuple(self.resolve(v) for v in value)

        if isinstance(value, list):
            return [self.resolve(v) for v in value]

        return value

    def normalize_outputs(
        self, result: Any, output_spec: Mapping[str, Any] | None, store: ArtifactStore
    ) -> NormalizedOutputs:
        """
        Normalize function outputs into a dict[str, Any].

        Rules:
        - If output_spec is None → {"return_value": result}
        - Tuple → positional mapping
        - Dict → key mapping
        - Single value → single output
        """
        if output_spec is None:
            return {"return_value": self.materialize(result, store)}

        output_keys = list(output_spec.keys())

        if len(output_keys) == 1:
            return {output_keys[0]: self.materialize(result, store)}

        if isinstance(result, dict):
            missing = set(output_keys) - result.keys()
            if missing:
                raise ValueError(f"Missing outputs in return dict: {missing}")
            return {k: self.materialize(result[k], store) for k in output_keys}

        if isinstance(result, tuple):
            if len(result) != len(output_keys):
                raise ValueError("Tuple output length does not match declared outputs")
            return {k: self.materialize(v, store) for k, v in zip(output_keys, result)}

        raise TypeError(
            f"Invalid return type for declared outputs. result: {result}, output_spec: {
                output_spec
            }",
        )

    def materialize(self, value: Any, store: ArtifactStore) -> Any:
        """
        Recursively materialize big objects.
        """
        if store.is_big(value):
            return store.save(value)

        if isinstance(value, dict):
            return {k: self.materialize(v, store) for k, v in value.items()}

        if isinstance(value, tuple):
            return tuple(self.materialize(v, store) for v in value)

        if isinstance(value, list):
            return [self.materialize(v, store) for v in value]

        return value
