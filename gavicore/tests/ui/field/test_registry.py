#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from gavicore.models import DataType, Schema
from gavicore.ui import (
    FieldBase,
    FieldContext,
    FieldFactory,
    FieldFactoryRegistry,
    FieldMeta,
)


class MyField(FieldBase):
    pass


class MyFieldFactoryBase(FieldFactory):
    def get_score(self, meta: FieldMeta) -> int:
        return 0

    def create_field(self, ctx: FieldContext) -> MyField:
        return MyField(ctx.vm.primitive(), object())


class MyFieldFactory1(MyFieldFactoryBase):
    def get_score(self, meta: FieldMeta) -> int:
        return 1 if meta.schema_.type == DataType.string else 0


class MyFieldFactory2(MyFieldFactory1):
    def get_score(self, meta: FieldMeta) -> int:
        return (
            2
            if meta.schema_.type == DataType.string and meta.schema_.format == "uri"
            else 0
        )


class MyFieldFactory3(MyFieldFactoryBase):
    def get_score(self, meta: FieldMeta) -> int:
        return (
            3
            if meta.schema_.type == DataType.string and meta.schema_.format == "date"
            else 0
        )


class FieldFactoryRegistryTest(TestCase):
    def test_register(self):
        f1 = MyFieldFactory1()
        f2 = MyFieldFactory2()
        f3 = MyFieldFactory3()
        r = FieldFactoryRegistry(f1)
        unregister_2 = r.register(f2)
        unregister_3 = r.register(f3)
        self.assertEqual({f1, f2, f3}, r.factories)
        unregister_2()
        self.assertEqual({f1, f3}, r.factories)
        unregister_3()
        self.assertEqual({f1}, r.factories)

    def test_find(self):
        f1 = MyFieldFactory1()
        f2 = MyFieldFactory2()
        f3 = MyFieldFactory3()
        r = FieldFactoryRegistry(f1, f2, f3)

        meta = _meta_from_schema({"type": "string"})
        self.assertEqual(f1, r.lookup(meta))

        meta = _meta_from_schema({"type": "string", "format": "uri"})
        self.assertEqual(f2, r.lookup(meta))

        meta = _meta_from_schema({"type": "string", "format": "date"})
        self.assertEqual(f3, r.lookup(meta))

        meta = _meta_from_schema({"type": "string", "format": "bbox"})
        self.assertEqual(f1, r.lookup(meta))

        meta = _meta_from_schema({"type": "array", "format": "bbox"})
        self.assertEqual(None, r.lookup(meta))


def _meta_from_schema(d: dict) -> FieldMeta:
    return FieldMeta.from_schema("root", Schema(**d))
