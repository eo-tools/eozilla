#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from gavicore.util.undefined import UNDEFINED, UndefinedType

from ..field.meta import FieldMeta
from .base import ViewModel
from .composite import CompositeViewModel


class ArrayViewModel(CompositeViewModel[int, list[Any]]):
    """
    A view model for a non-nullable, growable, sparse array value.
    """

    def __init__(self, meta: FieldMeta, *, value: Any | UndefinedType = UNDEFINED):
        super().__init__(meta, list, value)
        self._item_meta = meta.item
        # initialize item view models
        self._items: dict[int, ViewModel] = {}
        self._length: int = 0
        if isinstance(value, list):
            self._length = len(value)
            for i, v in enumerate(value):
                self._items[i] = self._create_child(self._item_meta, v)

    @property
    def items(self) -> list[ViewModel | None]:
        return [self._items.get(i) for i in range(self._length)]

    def _assemble_value(self) -> list[Any]:
        items = self._items
        value = []
        for i in range(self._length):
            if i in items:
                vm = items[i]
                v = vm._get_value()
            else:
                # or raise?
                v = self._item_meta.get_initial_value()
            value.append(v)
        return value

    def _distribute_value(self, value: list[Any]) -> None:
        new_length = len(value)
        old_length = self._length
        if new_length < old_length:
            # truncate array
            items = self._items
            for i in range(new_length, old_length):
                if i in items:
                    vm = items[i]
                    if vm is not None:
                        vm.dispose()
                    del items[i]
            self._length = new_length

        with self.intercept_changes() as changes:
            for i, v in enumerate(value):
                self._set_item(i, v)

        if changes or old_length != new_length:
            self._invalidate()
            self._notify(*changes)

    def __len__(self) -> int:
        return self._length

    def __getitem__(self, index: int) -> Any:
        items = self._items
        if index in items:
            vm = items[index]
            return vm._get_value()
        if index < self._length:
            return self._item_meta.get_initial_value()
        raise IndexError(f"index out of range for field {self.meta.name!r}")

    def __setitem__(self, index: int, value: Any) -> None:
        self._set_item(index, value)

    def _set_item(self, index: int, value: Any) -> None:
        old_length = self._length
        new_length = max(old_length, index + 1)
        self._length = new_length
        if index in self._items:
            child_vm = self._items[index]
            with child_vm.intercept_changes() as changes:
                child_vm._set_value(value)
            if changes or new_length != old_length:
                self._invalidate()
                self._notify(*changes)
        else:
            child_vm = self._create_child(self._item_meta, value)
            self._items[index] = child_vm
            self._invalidate()
            self._notify()
