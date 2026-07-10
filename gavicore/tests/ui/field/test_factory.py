#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from gavicore.models import Schema
from gavicore.ui import (
    FieldBase,
    FieldContext,
    FieldFactoryBase,
    FieldGenerator,
    FieldMeta,
)


class MyField(FieldBase):
    def _bind(self) -> None:
        pass


class MyFieldFactory(FieldFactoryBase):
    pass


def make_ctx(meta: FieldMeta):
    builder = FieldGenerator()
    return FieldContext(generator=builder, meta=meta)


class FieldFactoryBaseTest(TestCase):
    factory = MyFieldFactory()
    meta_nullable = FieldMeta.from_schema(
        "x", Schema(**{"type": "array", "nullable": True})
    )
    meta_boolean = FieldMeta.from_schema("x", Schema(**{"type": "boolean"}))
    meta_integer = FieldMeta.from_schema("x", Schema(**{"type": "integer"}))
    meta_number = FieldMeta.from_schema("x", Schema(**{"type": "number"}))
    meta_string = FieldMeta.from_schema("x", Schema(**{"type": "string"}))
    meta_array = FieldMeta.from_schema("x", Schema(**{"type": "array"}))
    meta_object = FieldMeta.from_schema("x", Schema(**{"type": "object"}))
    meta_one_of = FieldMeta.from_schema("x", Schema(**{"oneOf": []}))
    meta_any_of = FieldMeta.from_schema("x", Schema(**{"anyOf": []}))
    meta_all_of = FieldMeta.from_schema("x", Schema(**{"allOf": []}))
    meta_untyped = FieldMeta.from_schema("x", Schema(**{}))

    def test_get_score(self):
        f = self.factory
        self.assertEqual(0, f.get_score(self.meta_nullable))
        self.assertEqual(0, f.get_score(self.meta_boolean))
        self.assertEqual(0, f.get_score(self.meta_integer))
        self.assertEqual(0, f.get_score(self.meta_number))
        self.assertEqual(0, f.get_score(self.meta_string))
        self.assertEqual(0, f.get_score(self.meta_array))
        self.assertEqual(0, f.get_score(self.meta_object))
        self.assertEqual(0, f.get_score(self.meta_one_of))
        self.assertEqual(0, f.get_score(self.meta_any_of))
        self.assertEqual(0, f.get_score(self.meta_all_of))
        self.assertEqual(0, f.get_score(self.meta_untyped))

    def test_create_field(self):
        f = self.factory
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_nullable))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_boolean))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_integer))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_number))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_string))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_array))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_object))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_one_of))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_any_of))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_all_of))
        with pytest.raises(NotImplementedError):
            f.create_field(make_ctx(self.meta_untyped))
