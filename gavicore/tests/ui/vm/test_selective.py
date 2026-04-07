#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from gavicore.models import Schema
from gavicore.ui import FieldMeta
from gavicore.ui.vm import (
    ViewModel,
    SelectiveViewModel,
)
from gavicore.ui.vm.base import ViewModelChangeRecorder


class SelectiveViewModelTest(TestCase):
    option_schemas = [
        Schema(**{"type": "boolean"}),
        Schema(**{"type": "integer", "default": 137}),
        Schema(**{"type": "string", "default": "/data"}),
    ]
    meta = FieldMeta.from_schema("x", Schema(**{"oneOf": option_schemas}))

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

        with pytest.raises(
            ValueError, match="meta.one_of or meta.any_of must be given"
        ):
            SelectiveViewModel(
                FieldMeta.from_schema("x", Schema(**{})), options=self.options
            )

        with pytest.raises(
            ValueError,
            match="meta.one_of or meta.any_of must have the same length as options",
        ):
            SelectiveViewModel(self.meta, options=self.options + self.options)

        with pytest.raises(ValueError, match="active_index is out of bounds"):
            SelectiveViewModel(self.meta, options=self.options, active_index=3)
