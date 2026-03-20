#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from ..fieldmeta import UIFieldMeta
from .base import ViewModel, ViewModelChangeEvent

K = TypeVar("K", bound=str | int)
T = TypeVar("T", bound=dict[str, Any] | list[Any])
NoneType = type(None)


class CompositeViewModel(Generic[K, T], ViewModel[T | None], ABC):
    """
    An abstract base class for view model that
    are composites of child view models.
    """

    def __init__(
        self, field_meta: UIFieldMeta, initial_value: Any, composite_type: type[T]
    ):
        super().__init__(field_meta)
        CompositeViewModel._assert_value_is_valid(
            field_meta, initial_value, composite_type
        )
        self._composite_type = composite_type
        self._stale: bool = initial_value is not None
        self._cached_value: T | None = None
        self._children: dict[K, ViewModel] = {}

    @property
    def is_null(self) -> bool | None:
        if not self._stale:
            return self._cached_value is None
        # we don't know
        return None

    def get(self) -> T | None:
        if self._stale:
            self._cached_value = self._assemble_value()
            self._stale = False
        return self._cached_value

    def set(self, value: T | None) -> None:
        self._assert_value_is_valid(self._field_meta, value, self._composite_type)
        if not self._stale and value == self._cached_value:
            # No change
            return
        self._stale = value is not None
        self._cached_value = None
        if value is not None:
            self._distribute_value(value)

    @abstractmethod
    def _assemble_value(self) -> T:
        """Assemble a composite value from child view models."""

    @abstractmethod
    def _distribute_value(self, value: T) -> None:
        """Distribute a composite value to child view models."""

    @abstractmethod
    def __len__(self) -> int:
        """Length of the composite."""

    @abstractmethod
    def __getitem__(self, key: K) -> Any:
        """Get item by key."""

    @abstractmethod
    def __setitem__(self, key: K, value: Any) -> None:
        """Set item by key and value."""

    def _create_child(self, child_meta: UIFieldMeta, child_value: Any) -> ViewModel:
        child_vm = ViewModel.create(child_meta, child_value)
        child_vm.watch(self._on_child_change)
        return child_vm

    def _on_child_change(self, _event: ViewModelChangeEvent):
        if self.is_null:
            # child changes cannot have an effect if parent is null
            return
        self._stale = True
        self._cached_value = None

    def _assert_not_null(self) -> None:
        if self.is_null:
            raise ValueError(f"Field {self._field_meta.name!r} is None")

    @classmethod
    def _assert_value_is_valid(
        cls, field_meta: UIFieldMeta, value: Any, composite_type: type[T]
    ) -> None:
        if field_meta.schema_.nullable:
            # noinspection PyTypeHints
            if not isinstance(value, (composite_type, type(None))):
                raise ValueError(
                    f"Initial value must be a {composite_type.__name__} or None "
                    f"for field {field_meta.name!r} but was {value!r}"
                )
        else:
            if not isinstance(value, composite_type):
                raise ValueError(
                    f"Initial value must be a {composite_type.__name__} "
                    f"for field {field_meta.name!r} but was {value!r}"
                )
