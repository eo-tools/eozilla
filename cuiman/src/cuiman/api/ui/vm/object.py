#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from .base import UIFieldMeta, ViewModel, get_initial_value
from .composite import CompositeViewModel


class ObjectViewModel(CompositeViewModel[str, dict[str, Any]]):
    def __init__(self, field_meta: UIFieldMeta, parent: ViewModel | None, value: Any):
        super().__init__(field_meta, parent, value, dict)
        # initialize item view models
        for item_meta in field_meta.children:
            k = item_meta.name
            if isinstance(value, dict) and k in value:
                v = value[k]
            else:
                v = get_initial_value(item_meta)
            self._item_vms[k] = self._create_item_vm(item_meta, v)

    def get(self) -> dict[str, Any] | None:
        if self._stale:
            self._stale = False
            self._value = {k: vm.get() for k, vm in self._item_vms.items()}
        return self._value

    def set(self, value: dict[str, Any] | None) -> None:
        self._assert_value_is_valid(self._field_meta, value, dict)
        if value is not None:
            for k, v in value.items():
                vm = self._item_vms[k]
                vm.set(v)
        self._stale = value is not None
        self._value = None

    def __len__(self) -> int:
        self._assert_not_null()
        return len(self._item_vms)

    def __getitem__(self, key: str) -> Any:
        self._assert_not_null()
        vm = self._item_vms[key]
        return vm.get()

    def __setitem__(self, key: str, value: Any) -> None:
        self._assert_not_null()
        vm = self._item_vms[key]
        vm.set(value)
