#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from .._util import UNDEFINED, UndefinedType
from ..fieldmeta import UIFieldMeta
from .base import ViewModel
from .composite import CompositeViewModel


class ArrayViewModel(CompositeViewModel[int, list[Any]]):
    """
    A view model for a non-nullable, growable, sparse array value.
    """

    def __init__(
        self, field_meta: UIFieldMeta, initial_value: Any | UndefinedType = UNDEFINED
    ):
        super().__init__(field_meta, list, initial_value)
        assert field_meta.children is not None and len(field_meta.children) == 1
        self._item_meta = field_meta.children[0]
        # initialize item view models
        self._item_view_models: dict[int, ViewModel] = {}
        self._length: int = 0
        if isinstance(initial_value, list):
            self._length = len(initial_value)
            for i, v in enumerate(initial_value):
                self._item_view_models[i] = self._create_child(self._item_meta, v)

    def _assemble_value(self) -> list[Any]:
        item_view_models = self._item_view_models
        value = []
        for i in range(self._length):
            if i in item_view_models:
                vm = item_view_models[i]
                v = vm.get()
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
            item_view_models = self._item_view_models
            for i in range(new_length, old_length):
                if i in item_view_models:
                    vm = item_view_models[i]
                    if vm is not None:
                        vm.dispose()
                    del item_view_models[i]
            self._length = new_length

        for i, v in enumerate(value):
            self._set_item(i, v)

    def __len__(self) -> int:
        return self._length

    def __getitem__(self, index: int) -> Any:
        item_view_models = self._item_view_models
        if index in item_view_models:
            vm = item_view_models[index]
            return vm.get()
        return self._item_meta.get_initial_value()

    def __setitem__(self, index: int, value: Any) -> None:
        self._set_item(index, value)

    def _set_item(self, index: int, value: Any) -> None:
        if index in self._item_view_models:
            child_vm = self._item_view_models[index]
            child_vm.set(value)
        else:
            child_vm = self._create_child(self._item_meta, value)
            self._item_view_models[index] = child_vm
        self._length = max(self._length, index + 1)
