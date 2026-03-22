#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import TypeVar
from unittest import TestCase

from cuiman.api.ui import UIFieldMeta
from cuiman.api.ui.vm import (
    ArrayViewModel,
    NullableViewModel,
    ObjectViewModel,
    PrimitiveViewModel,
    ViewModel,
    ViewModelChangeEvent,
)
from gavicore.models import Schema

VM = TypeVar("VM", bound=ViewModel)


class MyViewModelObserver:
    def __init__(self):
        self.events: list[ViewModelChangeEvent] = []

    @property
    def change_count(self) -> int:
        return len(self.events)

    def __call__(self, event: ViewModelChangeEvent) -> None:
        self.events.append(event)


class ViewModelTest(TestCase):
    def test_primitive(self):
        meta = UIFieldMeta.from_schema("x", Schema(**{"type": "integer"}))
        self._assert_vm_basics(PrimitiveViewModel(meta, 137), 137, 138)

    def test_array(self):
        meta = UIFieldMeta.from_schema(
            "x", Schema(**{"type": "array", "items": {"type": "integer"}})
        )
        vm = self._assert_vm_basics(
            ArrayViewModel(meta, [10, 11]), [10, 11], [10, 11, 12]
        )

        self.assertEqual(3, len(vm))
        items = vm.items
        self.assertIsInstance(items, list)
        self.assertEqual(3, len(items))
        self.assertIsInstance(items[0], PrimitiveViewModel)
        self.assertIsInstance(items[1], PrimitiveViewModel)
        self.assertIsInstance(items[2], PrimitiveViewModel)
        vm[5] = 100
        self.assertEqual(6, len(vm))
        self.assertEqual([10, 11, 12, 0, 0, 100], vm.value)
        items = vm.items
        self.assertIsInstance(items, list)
        self.assertEqual(6, len(items))
        self.assertIsInstance(items[0], PrimitiveViewModel)
        self.assertIsInstance(items[1], PrimitiveViewModel)
        self.assertIsInstance(items[2], PrimitiveViewModel)
        self.assertIsNone(items[3])
        self.assertIsNone(items[4])
        self.assertIsInstance(items[5], PrimitiveViewModel)

    def test_object(self):
        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "object",
                    "properties": {"a": {"type": "boolean"}, "b": {"type": "string"}},
                }
            ),
        )
        vm = self._assert_vm_basics(
            ObjectViewModel(meta, {"a": True, "b": "ds.zarr"}),
            {"a": True, "b": "ds.zarr"},
            {"a": False, "b": "ds.zarr"},
        )
        properties = vm.properties
        self.assertIsInstance(properties, dict)
        self.assertEqual(["a", "b"], list(properties.keys()))
        self.assertIsInstance(properties["a"], PrimitiveViewModel)
        self.assertIsInstance(properties["b"], PrimitiveViewModel)

    def test_nullable(self):
        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "number",
                    "nullable": "true",
                }
            ),
        )
        vm = self._assert_vm_basics(NullableViewModel(meta, None), None, 2.1)
        self.assertEqual(False, vm.is_null)
        vm.value = None
        self.assertEqual(True, vm.is_null)

    def _assert_vm_basics(self, vm: VM, initial_value, other_value) -> VM:
        self.assertEqual(initial_value, vm.value)
        vm.value = other_value
        self.assertEqual(other_value, vm.value)

        observer = MyViewModelObserver()
        unwatch = vm.watch(observer)

        vm.value = initial_value
        self.assertEqual(1, observer.change_count)
        vm.value = initial_value
        self.assertEqual(1, observer.change_count)
        vm.value = other_value
        self.assertEqual(2, observer.change_count)
        vm.value = other_value
        self.assertEqual(2, observer.change_count)
        vm.value = initial_value
        self.assertEqual(3, observer.change_count)
        self.assertEqual(initial_value, vm.value)

        unwatch()
        vm.value = other_value
        self.assertEqual(3, observer.change_count)
        self.assertEqual(other_value, vm.value)

        return vm
