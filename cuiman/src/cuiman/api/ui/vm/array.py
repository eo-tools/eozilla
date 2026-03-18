#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from .base import UIFieldMeta, ViewModel, get_initial_value
from .composite import CompositeViewModel


class ArrayViewModel(CompositeViewModel[int, list[Any]]):
    def __init__(self, field_meta: UIFieldMeta, parent: ViewModel | None, value: Any):
        super().__init__(field_meta, parent, value, list)
        # initialize item view models
        item_fi = self.item_meta
        self._length: int = 0
        if isinstance(value, list):
            self._length = len(value)
            for i, v in enumerate(value):
                self._item_vms[i] = self._create_item_vm(item_fi, v)

    @property
    def item_meta(self) -> UIFieldMeta:
        return self._field_meta.children[0]

    def get(self) -> list[Any] | None:
        if self._stale:
            item_meta = self.item_meta
            self._stale = False
            self._value = []
            for i in range(self._length):
                if i in self._item_vms:
                    vm = self._item_vms[i]
                    v = vm.get()
                else:
                    # or raise?
                    v = get_initial_value(item_meta)
                self._value.append(v)
        return self._value

    def set(self, value: list[Any] | None) -> None:
        self._assert_value_is_valid(self._field_meta, value, list)
        if value is not None:
            for i, v in enumerate(value):
                self._set_item(i, v)
        self._stale = value is not None
        self._value = None

    def __len__(self) -> int:
        self._assert_not_null()
        return self._length

    def __getitem__(self, index: int) -> Any:
        self._assert_not_null()
        if index in self._item_vms:
            vm = self._item_vms[index]
            return vm.get()
        item_meta = self._field_meta.children[0]
        return get_initial_value(item_meta)

    def __setitem__(self, index: int, value: Any) -> None:
        self._assert_not_null()
        self._set_item(index, value)

    def _set_item(self, index: int, value: Any) -> None:
        if index in self._item_vms:
            vm = self._item_vms[index]
            vm.set(value)
        else:
            self._item_vms[index] = self._create_item_vm(self.item_meta, value)
            self._length = max(self._length, index + 1)
