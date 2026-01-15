from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping, Union

import xarray as xr

NormalizedOutputs = dict[str, Any]


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    loader: str

class ArtifactStore(ABC):
    """
    Abstract base class for persisting and loading large objects
    (e.g. xarray datasets, large arrays, model artifacts).

    Concrete implementations define how objects are stored
    (filesystem, object store, etc.).
    """

    @abstractmethod
    def is_big(self, obj: Any) -> bool:
        """
        Determine whether an object should be treated as a 'big object'
        and stored externally instead of being passed as is.

        Args:
            obj: Object to inspect.

        Returns:
            True if the object is considered large and should be stored
            via this store, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def save(self, obj: Any) -> ArtifactRef:
        """
        Persist a large object and return a reference to it.

        Args:
            obj: The object to be stored.

        Returns:
            ArtifactRef: A reference that can later be used to load the object.

        Raises:
            TypeError: If the object type is not supported by the implementation.
        """
        raise NotImplementedError

    @abstractmethod
    def load(self, ref: ArtifactRef) -> Any:
        """
        Load a previously stored object using an ArtifactRef.

        Args:
            ref: Reference returned by `save`.

        Returns:
            The reconstructed object.

        Raises:
            ValueError: If the loader specified in the reference is unknown.
        """
        raise NotImplementedError


class NullArtifactStore(ArtifactStore):
    """
    No-op artifact store.

    This store never treats objects as 'big' and does not
    support saving or loading artifacts.
    """

    def is_big(self, obj: Any) -> bool:
        """
        No object is considered big in the null store.
        """
        return False

    def save(self, obj: Any):
        """
        Saving artifacts is not supported in the null store.
        """
        raise RuntimeError("NullArtifactStore does not support saving artifacts")

    def load(self, ref):
        """
        Loading artifacts is not supported in the null store.
        """
        raise RuntimeError("NullArtifactStore does not support loading artifacts")


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
            f"Invalid return type for declared outputs. result: {result}, output_spec: {output_spec}",
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
