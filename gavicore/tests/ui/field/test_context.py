#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import Any, Literal
from unittest import TestCase

import pytest

from gavicore.models import Schema
from gavicore.ui import (
    FieldContext,
    FieldGenerator,
    FieldMeta,
)


class FieldContextTest(TestCase):
    def test_primitive(self):
        meta = FieldMeta.from_schema(
            "threshold",
            Schema(
                **{
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                }
            ),
        )

        generator = FieldGenerator()
        ctx = FieldContext(
            generator=generator,
            meta=meta,
            initial_value=0.5,
            parent_ctx=None,
        )

        self.assertIs(meta, ctx.meta)
        self.assertIs(generator, ctx._generator)
        self.assertEqual(["threshold"], ctx.path)

    def test_label_hidden(self):
        meta = FieldMeta.from_schema(
            "threshold",
            Schema(
                **{
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                }
            ),
        )

        generator = FieldGenerator()
        ctx = FieldContext(
            generator=generator,
            meta=meta,
            initial_value=0.5,
            label_hidden=True,
        )

        self.assertIs(meta, ctx.meta)
        self.assertIs(True, ctx.label_hidden)
        self.assertEqual("", ctx.label)

    def test_child_ctx(self):
        meta = FieldMeta.from_schema(
            "config",
            Schema(
                **{
                    "type": "object",
                    "properties": {
                        "threshold": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        }
                    },
                }
            ),
        )

        generator = FieldGenerator()
        ctx = FieldContext(
            generator=generator,
            meta=meta,
            initial_value=0.5,
            parent_ctx=None,
        )

        self.assertIs(meta, ctx.meta)
        self.assertIs(generator, ctx._generator)
        self.assertEqual(["config"], ctx.path)

        child_ctx = ctx._create_child_ctx(meta.properties["threshold"])
        self.assertIs(generator, child_ctx._generator)
        self.assertEqual(["config", "threshold"], child_ctx.path)


class FieldContextLayoutTest(TestCase):
    @classmethod
    def layout_fn(
        cls,
        _ctx: FieldContext,
        direction: Literal["row", "column"],
        child_views: list[Any],
    ) -> Any:
        return direction, *child_views

    @classmethod
    def create_ctx_and_views(cls, layout: Any) -> tuple[FieldContext, dict[str, Any]]:
        ctx = FieldContext(
            generator=FieldGenerator(),
            meta=FieldMeta.from_schema(
                "x",
                Schema(
                    **{
                        "type": "object",
                        "properties": {
                            "a": {"type": "string"},
                            "b": {"type": "string"},
                            "c": {"type": "string"},
                            "d": {"type": "string"},
                            "e": {"type": "string"},
                            "f": {"type": "string"},
                        },
                        "x-ui-layout": layout,
                    }
                ),
            ),
        )
        return ctx, {k: f"v({k})" for k in ctx.meta.properties.keys()}

    def test_layout_row(self):
        ctx, child_views = self.create_ctx_and_views("row")
        self.assertEqual(
            ("row", *child_views.values()), ctx.layout(self.layout_fn, child_views)
        )

    def test_layout_column(self):
        ctx, child_views = self.create_ctx_and_views("column")
        self.assertEqual(
            ("column", *child_views.values()), ctx.layout(self.layout_fn, child_views)
        )

    def test_layout_nested(self):
        ctx, child_views = self.create_ctx_and_views(
            {
                "type": "row",
                "items": [
                    {
                        "type": "column",
                        "items": [
                            "a",
                            {
                                "type": "row",
                                "items": ["b", "c"],
                            },
                        ],
                    },
                    {
                        "type": "column",
                        "items": [
                            {
                                "type": "row",
                                "items": ["d", "e"],
                            },
                            "f",
                        ],
                    },
                ],
            }
        )
        self.assertEqual(
            (
                "row",
                (
                    "column",
                    "v(a)",
                    (
                        "row",
                        "v(b)",
                        "v(c)",
                    ),
                ),
                (
                    "column",
                    (
                        "row",
                        "v(d)",
                        "v(e)",
                    ),
                    "v(f)",
                ),
            ),
            ctx.layout(self.layout_fn, child_views),
        )

    @classmethod
    def create_ctx_and_views_ordered(
        cls, layout: Any
    ) -> tuple[FieldContext, dict[str, Any]]:
        ctx = FieldContext(
            generator=FieldGenerator(),
            meta=FieldMeta.from_schema(
                "x",
                Schema(
                    **{
                        "type": "object",
                        "properties": {
                            "a": {"type": "string", "x-ui-order": 11},
                            "b": {"type": "string", "x-ui-order": 20},
                            "c": {"type": "string", "x-ui-order": 30},
                            "d": {"type": "string", "x-ui-order": 20},
                            "e": {"type": "string", "x-ui-order": 20},
                            "f": {"type": "string", "x-ui-order": 10},
                        },
                        "x-ui-layout": layout,
                    }
                ),
            ),
        )
        return ctx, {k: f"v({k})" for k in ctx.meta.properties.keys()}

    def test_layout_ordered(self):
        ctx, child_views = self.create_ctx_and_views_ordered("column")
        self.assertEqual(
            ("column", "v(f)", "v(a)", "v(b)", "v(d)", "v(e)", "v(c)"),
            ctx.layout(self.layout_fn, child_views),
        )

    def test_layout_fail(self):
        ctx, child_views = self.create_ctx_and_views(
            {"type": "row", "items": ["a", "p", "c"]}
        )
        with pytest.raises(
            ValueError, match="property 'p' not found in object field 'x'"
        ):
            ctx.layout(self.layout_fn, child_views)
