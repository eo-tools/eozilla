#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from gavicore.util.undefined import UNDEFINED, UndefinedType

from ..field.meta import UIFieldMeta
from .base import ViewModel
from .composite import CompositeViewModel


class ObjectViewModelBase(CompositeViewModel[str, dict[str, Any]]):
    """
    A view model for a non-nullable, static object
    comprising view models for each of its properties.
    """

    def __init__(
        self,
        meta: UIFieldMeta,
        value: Any | UndefinedType,
    ):
        super().__init__(meta, dict, value)
        self._properties: dict[str, ViewModel] = {}

    @property
    def properties(self) -> dict[str, ViewModel]:
        return dict(self._properties)

    def _assemble_value(self) -> dict[str, Any]:
        return {k: vm._get_value() for k, vm in self._properties.items()}

    def _distribute_value(self, value: dict[str, Any]) -> None:
        for k, v in value.items():
            vm = self._properties[k]
            vm._set_value(v)

    def __len__(self) -> int:
        return len(self._properties)

    def __getitem__(self, key: str) -> Any:
        vm = self._properties[key]
        return vm._get_value()

    def __setitem__(self, key: str, value: Any) -> None:
        vm = self._properties[key]
        vm._set_value(value)


class ObjectViewModel(ObjectViewModelBase):
    """
    A view model for a non-nullable, static object
    comprising view models for each of its properties.
    """

    def __init__(
        self,
        meta: UIFieldMeta,
        *,
        value: Any | UndefinedType = UNDEFINED,
        properties: dict[str, ViewModel] | None = None,
    ):
        super().__init__(meta, value)
        # initialize item view models
        for k, child_meta in meta.properties.items():
            vm = properties.get(k) if properties else None
            if vm is not None:
                if vm.meta is not child_meta:
                    raise ValueError(
                        f"invalid view model passed for property {k!r} "
                        f"of field {meta.name!r}"
                    )
                vm.watch(self._on_child_change)
            else:
                if isinstance(value, dict) and k in value:
                    v = value[k]
                else:
                    v = child_meta.get_initial_value()
                vm = self._create_child(child_meta, v)
            self._properties[k] = vm


class DynamicObjectViewModel(ObjectViewModelBase):
    """
    A view model for a non-nullable, static object
    comprising view models for each of its properties.
    """

    def __init__(self, meta: UIFieldMeta):
        super().__init__(meta, UNDEFINED)
        self._frozen = False

    def define_property(self, prop_name: str, prop_vm: ViewModel) -> None:
        if self._frozen:
            raise ValueError("cannot define properties after freeze() was called")
        if prop_name not in self.meta.properties:
            raise ValueError(
                f"property {prop_name!r} not found in field {self.meta.name!r}"
            )
        self._properties[prop_name] = prop_vm
        self._invalidate()

    def freeze(self):
        # Define all yet undefined properties from meta.properties
        properties = dict(self.meta.properties)
        for prop_name, prop_meta in properties.items():
            if prop_name not in properties:
                v = prop_meta.get_initial_value()
                prop_vm = self._create_child(prop_meta, v)
                self.define_property(prop_name, prop_vm)
        self._frozen = True
