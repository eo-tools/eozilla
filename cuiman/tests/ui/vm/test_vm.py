#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from cuiman.ui import UIFieldMeta
from cuiman.ui.vm import (
    ArrayViewModel,
    NullableViewModel,
    ObjectViewModel,
    PrimitiveViewModel,
    ViewModel,
    ViewModelChangeEvent,
)
from gavicore.models import Schema


class MyViewModelObserver:
    def __init__(self):
        self.events: list[ViewModelChangeEvent] = []

    @property
    def change_count(self) -> int:
        return len(self.events)

    def __call__(self, event: ViewModelChangeEvent) -> None:
        self.events.append(event)


# noinspection PyMethodMayBeStatic
class ViewModelTest(TestCase):
    def test_create_ok(self):
        meta = UIFieldMeta.from_schema(
            "x", Schema(**{"type": "integer", "default": -1})
        )
        vm = ViewModel.create(meta)
        self.assertIsInstance(vm, PrimitiveViewModel)
        self.assertEqual(-1, vm.value)

        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "array",
                    "items": {"type": "number"},
                    "default": [0.1, 0.5],
                }
            ),
        )
        vm = ViewModel.create(meta)
        self.assertIsInstance(vm, ArrayViewModel)
        self.assertEqual([0.1, 0.5], vm.value)

        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                    "default": {"x": 10, "y": -20},
                }
            ),
        )
        vm = ViewModel.create(meta)
        self.assertIsInstance(vm, ObjectViewModel)
        self.assertEqual({"x": 10, "y": -20}, vm.value)

        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "string",
                    "nullable": True,
                    "default": None,
                }
            ),
        )
        vm = ViewModel.create(meta)
        self.assertIsInstance(vm, NullableViewModel)
        self.assertEqual(None, vm.value)

    def test_create_failing(self):
        meta = UIFieldMeta.from_schema("x", Schema(**{}))
        with pytest.raises(ValueError, match="missing type in schema for field 'x'"):
            ViewModel.create(meta)

    def test_primitive_ok(self):
        meta = UIFieldMeta.from_schema("x", Schema(**{"type": "integer"}))
        vm = PrimitiveViewModel(meta, value=137)
        self._assert_vm_commons(vm, 137, 138)

    def test_primitive_failing(self):
        with pytest.raises(TypeError, match="meta must have type UIFieldMeta"):
            # noinspection PyTypeChecker
            PrimitiveViewModel(bool, value=True)

        meta = UIFieldMeta.from_schema(
            "x", Schema(**{"type": "integer", "nullable": True})
        )
        with pytest.raises(ValueError, match="meta must not be nullable"):
            PrimitiveViewModel(meta, value=137)

        meta = UIFieldMeta.from_schema("x", Schema(**{"type": "integer"}))
        with pytest.raises(ValueError, match="value must not be None"):
            PrimitiveViewModel(meta, value=None)

    def test_array_ok(self):
        meta = UIFieldMeta.from_schema(
            "x", Schema(**{"type": "array", "items": {"type": "integer"}})
        )
        vm = ArrayViewModel(meta, value=[10, 11])
        self._assert_vm_commons(vm, [10, 11], [10, 11, 12])

        self.assertEqual(3, len(vm))
        items = vm.items
        self.assertIsInstance(items, list)
        self.assertEqual(3, len(items))
        self.assertIsInstance(items[0], PrimitiveViewModel)
        self.assertIsInstance(items[1], PrimitiveViewModel)
        self.assertIsInstance(items[2], PrimitiveViewModel)
        vm[5] = 100
        self.assertEqual(100, vm[5])
        self.assertEqual(0, vm[3])
        self.assertEqual(0, vm[4])
        self.assertEqual(6, len(vm))
        self.assertEqual([10, 11, 12, 0, 0, 100], vm.value)
        vm[4] = 99
        self.assertEqual(99, vm[4])
        self.assertEqual([10, 11, 12, 0, 99, 100], vm.value)
        vm[5] = 17
        self.assertEqual(17, vm[5])
        self.assertEqual([10, 11, 12, 0, 99, 17], vm.value)
        items = vm.items
        self.assertIsInstance(items, list)
        self.assertEqual(6, len(items))
        self.assertIsInstance(items[0], PrimitiveViewModel)
        self.assertIsInstance(items[1], PrimitiveViewModel)
        self.assertIsInstance(items[2], PrimitiveViewModel)
        self.assertIsNone(items[3])
        self.assertIsInstance(items[4], PrimitiveViewModel)
        self.assertIsInstance(items[5], PrimitiveViewModel)

    def test_array_failing(self):
        meta = UIFieldMeta.from_schema(
            "x",
            Schema(**{"type": "array", "nullable": True, "items": {"type": "integer"}}),
        )
        with pytest.raises(ValueError, match="meta must not be nullable"):
            ArrayViewModel(meta)

        meta = UIFieldMeta.from_schema(
            "x", Schema(**{"type": "array", "items": {"type": "integer"}})
        )
        with pytest.raises(
            TypeError, match="value must be a list for field 'x' but was {10, 11}"
        ):
            ArrayViewModel(meta, value={10, 11})

        vm = ArrayViewModel(meta, value=[10, 11])
        with pytest.raises(
            IndexError,
            match="index out of range for field 'x'",
        ):
            # noinspection PyStatementEffect
            _x = vm[5]

    def test_object_ok(self):
        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "object",
                    "properties": {"a": {"type": "boolean"}, "b": {"type": "string"}},
                }
            ),
        )
        vm = ObjectViewModel(meta, value={"a": True, "b": "ds.zarr"})
        self._assert_vm_commons(
            vm,
            {"a": True, "b": "ds.zarr"},
            {"a": False, "b": "ds.zarr"},
        )
        properties = vm.properties
        self.assertIsInstance(properties, dict)
        self.assertEqual(["a", "b"], list(properties.keys()))
        self.assertIsInstance(properties["a"], PrimitiveViewModel)
        self.assertIsInstance(properties["b"], PrimitiveViewModel)

        self.assertEqual(False, vm["a"])
        self.assertEqual("ds.zarr", vm["b"])
        vm["a"] = True
        vm["b"] = "ds.tiff"
        self.assertEqual(True, vm["a"])
        self.assertEqual("ds.tiff", vm["b"])

        vm = ObjectViewModel(meta, properties={})
        self.assertEqual({"a": False, "b": ""}, vm.value)

    def test_object_failing(self):
        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "a": {"type": "boolean"},
                        "b": {"type": "string"},
                    },
                }
            ),
        )
        with pytest.raises(ValueError, match="meta must not be nullable"):
            ObjectViewModel(meta)

        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "object",
                    "properties": {
                        "a": {"type": "boolean"},
                        "b": {"type": "string"},
                    },
                }
            ),
        )
        with pytest.raises(
            TypeError,
            match=r"value must be a dict for field 'x' but was \[True, 'ds.zarr'\]",
        ):
            ObjectViewModel(meta, value=[True, "ds.zarr"])

        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "object",
                    "properties": {
                        "a": {"type": "boolean"},
                        "b": {"type": "string"},
                    },
                }
            ),
        )
        with pytest.raises(
            ValueError,
            match=r"invalid view model passed for property 'b' of field 'x'",
        ):
            ObjectViewModel(
                meta,
                properties={
                    "a": PrimitiveViewModel(meta.properties["a"]),
                    "b": PrimitiveViewModel(meta.properties["a"]),
                },
            )

    def test_nullable_ok(self):
        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "number",
                    "nullable": True,
                }
            ),
        )
        vm = NullableViewModel(meta, value=None)
        self._assert_vm_commons(vm, None, 2.1)
        self.assertIsInstance(vm.inner, PrimitiveViewModel)
        self.assertEqual(False, vm.is_null)
        vm.value = None
        self.assertEqual(True, vm.is_null)

    def test_nullable_failing(self):
        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "number",
                    "nullable": False,
                }
            ),
        )
        with pytest.raises(ValueError, match="meta must be nullable"):
            NullableViewModel(meta, value=None)

        meta = UIFieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "type": "number",
                    "nullable": True,
                }
            ),
        )
        with pytest.raises(ValueError, match="inner view model must not be nullable"):
            NullableViewModel(meta, inner=NullableViewModel(meta))

    def _assert_vm_commons(self, vm: ViewModel, initial_value, other_value):
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
