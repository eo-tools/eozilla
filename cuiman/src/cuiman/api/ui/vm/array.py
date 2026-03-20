#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from ..fieldmeta import UIFieldMeta
from .composite import CompositeViewModel


class ArrayViewModel(CompositeViewModel[int, list[Any]]):
    """A view model for a nullable, growable, sparse array."""

    def __init__(self, field_meta: UIFieldMeta, initial_value: Any):
        super().__init__(field_meta, initial_value, list)
        # initialize item view models
        item_meta = self.item_meta
        self._length: int = 0
        if isinstance(initial_value, list):
            self._length = len(initial_value)
            for i, v in enumerate(initial_value):
                self._children[i] = self._create_child(item_meta, v)

    @property
    def item_meta(self) -> UIFieldMeta:
        assert (
            self._field_meta.children is not None
            and len(self._field_meta.children) == 1
        )
        return self._field_meta.children[0]

    def _assemble_value(self) -> list[Any]:
        item_meta = self.item_meta
        value = []
        for i in range(self._length):
            if i in self._children:
                vm = self._children[i]
                v = vm.get()
            else:
                # or raise?
                v = item_meta.get_initial_value()
            value.append(v)
        return value

    def _distribute_value(self, value: list[Any]) -> None:
        new_length = len(value)
        old_length = self._length
        if new_length < old_length:
            # truncate array
            for i in range(new_length, old_length):
                if i in self._children:
                    vm = self._children[i]
                    if vm is not None:
                        vm.dispose()
                    del self._children[i]
            self._length = new_length

        for i, v in enumerate(value):
            self._set_item(i, v)

    def __len__(self) -> int:
        self._assert_not_null()
        return self._length

    def __getitem__(self, index: int) -> Any:
        self._assert_not_null()
        if index in self._children:
            vm = self._children[index]
            return vm.get()
        item_meta = self.item_meta
        return item_meta.get_initial_value()

    def __setitem__(self, index: int, value: Any) -> None:
        self._assert_not_null()
        self._set_item(index, value)

    def _set_item(self, index: int, value: Any) -> None:
        if index in self._children:
            child_vm = self._children[index]
            child_vm.set(value)
        else:
            child_vm = self._create_child(self.item_meta, value)
            self._children[index] = child_vm
        self._length = max(self._length, index + 1)
