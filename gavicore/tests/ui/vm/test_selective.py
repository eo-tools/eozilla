#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from gavicore.models import Schema
from gavicore.ui import FieldMeta
from gavicore.ui.vm import (
    SelectiveViewModel,
    ViewModel,
)
from gavicore.ui.vm.base import ViewModelChangeRecorder


class SelectiveViewModelTest(TestCase):
    def setUp(self):
        self.option_schemas = [
            Schema(**{"type": "boolean"}),
            Schema(**{"type": "integer", "default": 137}),
            Schema(**{"type": "string", "default": "/data"}),
        ]
        self.meta = FieldMeta.from_schema(
            "x",
            Schema(**{"oneOf": self.option_schemas}),
        )
        self.options = [
            ViewModel.from_field_meta(FieldMeta.from_schema(f"option_{i}", s))
            for i, s in enumerate(self.option_schemas)
        ]

    def test_value_access_ok(self):
        vm = SelectiveViewModel(self.meta, options=self.options)

        observer = ViewModelChangeRecorder()
        vm.watch(observer)

        self.assertEqual(0, vm.active_index)
        self.assertEqual(False, vm.value)

        vm.active_index = 1
        self.assertEqual(1, vm.active_index)
        self.assertEqual(137, vm.value)
        self.assertEqual(1, len(observer.change_events))

        vm.active_index = 2
        self.assertEqual(2, vm.active_index)
        self.assertEqual("/data", vm.value)
        self.assertEqual(2, len(observer.change_events))

        vm.value = "s3://xc-data"
        self.assertEqual(2, vm.active_index)
        self.assertEqual("s3://xc-data", vm.value)
        self.assertEqual(3, len(observer.change_events))

        vm.dispose()
        self.assertEqual(set(), vm._observers)
        for option in self.options:
            self.assertEqual(set(), option._observers)

    def test_ctor_fails(self):
        with pytest.raises(
            TypeError, match="meta must have type FieldMeta, but was int"
        ):
            # noinspection PyTypeChecker
            SelectiveViewModel(12, options=[])

        with pytest.raises(TypeError, match="options must have type list, but was int"):
            # noinspection PyTypeChecker
            SelectiveViewModel(self.meta, options=13)

        with pytest.raises(
            TypeError, match="active_index must have type int, but was NoneType"
        ):
            # noinspection PyTypeChecker
            SelectiveViewModel(self.meta, options=self.options, active_index=None)

        with pytest.raises(ValueError, match="active_index is out of bounds"):
            SelectiveViewModel(self.meta, options=self.options, active_index=3)


definitions = {
    "components": {
        "schemas": {
            "Point": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "coordinates": {"$ref": "#/components/schemas/Coordinate"},
                },
                "required": ["type", "coordinates"],
            },
            "LineString": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "coordinates": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Coordinate"},
                        "minItems": 2,
                    },
                },
                "required": ["type", "coordinates"],
            },
            "Polygon": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "coordinates": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Coordinate"},
                            "minItems": 3,
                        },
                        "minItems": 1,
                    },
                },
                "required": ["type", "coordinates"],
            },
            "Coordinate": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 3,
            },
        }
    },
}


class SelectiveViewModelWithDiscriminatorTest(TestCase):
    @classmethod
    def create_field_meta(
        cls, mapping: dict | None
    ) -> tuple[FieldMeta, list[ViewModel]]:
        options = [
            {"$ref": "#/components/schemas/Point"},
            {"$ref": "#/components/schemas/LineString"},
            {"$ref": "#/components/schemas/Polygon"},
        ]
        meta = FieldMeta.from_schema(
            "x",
            Schema(
                **{
                    "oneOf": options,
                    "discriminator": {
                        "propertyName": "type",
                        **({"mapping": mapping} if mapping else {}),
                    },
                    **definitions,
                }
            ),
        )
        options = [ViewModel.from_field_meta(m) for i, m in enumerate(meta.one_of)]
        return meta, options

    def test_value_access_without_mapping(self):
        self._assert_discriminator_works(
            mapping=None, expected_values=["Point", "LineString", "Polygon"]
        )

    def test_value_access_with_mapping(self):
        self._assert_discriminator_works(
            mapping={
                "ls": "#/components/schemas/LineString",
                "pg": "#/components/schemas/Polygon",
                "pt": "#/components/schemas/Point",
            },
            expected_values=["pt", "ls", "pg"],
        )

    def _assert_discriminator_works(
        self, mapping: dict | None, expected_values: list[str]
    ):
        meta, options = self.create_field_meta(mapping=mapping)

        vm = SelectiveViewModel(
            meta, options=options, discriminator=meta.schema_.discriminator
        )

        observer = ViewModelChangeRecorder()
        vm.watch(observer)

        self.assertEqual(0, vm.active_index)
        self.assertEqual(
            {"type": expected_values[0], "coordinates": [0.0, 0.0]}, vm.value
        )

        vm.active_index = 1
        self.assertEqual(1, vm.active_index)
        self.assertEqual(
            {"type": expected_values[1], "coordinates": [[0.0, 0.0], [0.0, 0.0]]},
            vm.value,
        )
        self.assertEqual(1, len(observer.change_events))

        vm.active_index = 2
        self.assertEqual(2, vm.active_index)
        self.assertEqual(
            {
                "type": expected_values[2],
                "coordinates": [[[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]],
            },
            vm.value,
        )
        self.assertEqual(2, len(observer.change_events))
