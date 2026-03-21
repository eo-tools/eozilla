#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from .._util import UNDEFINED, UndefinedType
from ..fieldmeta import UIFieldMeta
from .base import ViewModel
from .composite import CompositeViewModel


class ObjectViewModel(CompositeViewModel[str, dict[str, Any]]):
    """
    A view model for a non-nullable, static object
    comprising view models for each of its properties.
    """

    def __init__(
        self,
        field_meta: UIFieldMeta,
        initial_value: Any | UndefinedType = UNDEFINED,
        property_view_models: dict[str, ViewModel] | None = None,
    ):
        super().__init__(field_meta, dict, initial_value)
        self._property_view_models: dict[str, ViewModel] = {}
        # initialize item view models
        for child_meta in field_meta.children or []:
            k = child_meta.name
            vm = property_view_models.get(k) if property_view_models else None
            if vm is not None:
                if vm.field_meta is not child_meta:
                    raise ValueError(
                        f"View model for field {field_meta.name}: "
                        f"invalid view model passed for property {k!r}"
                    )
                vm.watch(self._on_child_change)
            else:
                if isinstance(initial_value, dict) and k in initial_value:
                    v = initial_value[k]
                else:
                    v = child_meta.get_initial_value()
                vm = self._create_child(child_meta, v)
            self._property_view_models[k] = vm

    def _assemble_value(self) -> dict[str, Any]:
        return {k: vm.get() for k, vm in self._property_view_models.items()}

    def _distribute_value(self, value: dict[str, Any]) -> None:
        for k, v in value.items():
            vm = self._property_view_models[k]
            vm.set(v)

    @property
    def property_view_models(self) -> dict[str, ViewModel]:
        return dict(self._property_view_models)

    def __len__(self) -> int:
        return len(self._property_view_models)

    def __getitem__(self, key: str) -> Any:
        vm = self._property_view_models[key]
        return vm.get()

    def __setitem__(self, key: str, value: Any) -> None:
        vm = self._property_view_models[key]
        vm.set(value)
