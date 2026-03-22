#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from .._util import UNDEFINED, UndefinedType
from ..fieldmeta import UIFieldMeta
from .base import ViewModel, ViewModelChangeEvent

K = TypeVar("K", str, int)
T = TypeVar("T", dict[str, Any], list[Any])


class CompositeViewModel(Generic[K, T], ViewModel[T], ABC):
    """
    An abstract base class for view model that
    are non-nullable composites of child view models.
    """

    def __init__(
        self,
        field_meta: UIFieldMeta,
        composite_type: type[T],
        initial_value: T | UndefinedType,
    ):
        super().__init__(field_meta)
        if field_meta.nullable:
            raise ValueError("field_meta must not be nullable")
        CompositeViewModel._assert_value_is_valid(
            field_meta, composite_type, initial_value
        )
        self._composite_type: type[T] = composite_type
        self._cached_value: T | UndefinedType = initial_value

    def _get_value(self) -> T:
        if not isinstance(self._cached_value, UndefinedType):
            return self._cached_value
        cached_value = self._assemble_value()
        assert UndefinedType.is_defined(cached_value)
        self._cached_value = cached_value
        return cached_value

    def _set_value(self, value: T) -> None:
        self._assert_value_is_valid(self._field_meta, self._composite_type, value)
        if self._is_valid() and self._cached_value == value:
            # No change
            return
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
        child_vm = self.create(child_meta, child_value)
        child_vm.watch(self._on_child_change)
        return child_vm

    def _on_child_change(self, event: ViewModelChangeEvent):
        self._invalidate()
        self._notify(event)

    @classmethod
    def _assert_value_is_valid(
        cls,
        field_meta: UIFieldMeta,
        composite_type: type[T],
        value: Any | UndefinedType,
    ) -> None:
        # noinspection PyTypeHints
        if not isinstance(value, (composite_type, UndefinedType)):
            raise ValueError(
                f"Value must be a {composite_type.__name__} "
                f"for field {field_meta.name!r} but was {value!r}"
            )

    def _is_valid(self) -> bool:
        return UndefinedType.is_defined(self._cached_value)

    def _invalidate(self) -> None:
        self._cached_value = UNDEFINED
