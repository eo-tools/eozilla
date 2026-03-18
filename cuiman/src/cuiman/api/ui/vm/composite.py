#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from .base import UIFieldMeta, ViewModel, ViewModelChangeEvent

K = TypeVar("K", bound=str | int)
T = TypeVar("T", bound=dict | list)


class CompositeViewModel(Generic[K, T], ViewModel[T], ABC):
    def __init__(
        self,
        field_meta: UIFieldMeta,
        parent: ViewModel | None,
        value: Any,
        value_type: type[T],
    ):
        super().__init__(field_meta, parent)
        CompositeViewModel._assert_value_is_valid(field_meta, value, value_type)
        self._stale = value is not None  # Not stale if initial_value is None
        self._value = None  # valid, if not stale
        self._item_vms: dict[K, ViewModel] = {}

    @property
    def is_null(self) -> bool | None:
        if not self._stale:
            return self._value is None
        # we don't know
        return None

    @abstractmethod
    def __len__(self) -> int:
        """Length of the composite."""

    @abstractmethod
    def __getitem__(self, key: K) -> Any:
        """Get item by key."""

    @abstractmethod
    def __setitem__(self, key: K, value: Any) -> None:
        """Set item by key and value."""

    def _create_item_vm(self, item_meta: UIFieldMeta, item_value: Any) -> ViewModel:
        item_vm = ViewModel.create(item_meta, self, item_value)
        item_vm.watch(self._on_item_change)
        return item_vm

    def _on_item_change(self, _event: ViewModelChangeEvent):
        self._stale = True
        self._value = None

    def _assert_not_null(self) -> None:
        if self.is_null:
            raise ValueError(f"Field {self._field_meta.name!r} is None")

    @classmethod
    def _assert_value_is_valid(
        cls, field_meta: UIFieldMeta, value: Any, data_type: type[T]
    ) -> None:
        if field_meta.schema_.nullable:
            # noinspection PyTypeHints
            if not isinstance(value, (data_type, type(None))):
                raise ValueError(
                    f"Initial value must be a {data_type.__name__} or None "
                    f"for {field_meta.name!r}"
                )
        else:
            if not isinstance(value, data_type):
                raise ValueError(
                    f"Initial value must be a {data_type.__name__} "
                    f"for {field_meta.name!r}"
                )
