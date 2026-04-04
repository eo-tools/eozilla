#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Generic, Literal, Protocol

from gavicore.models import DataType
from gavicore.util.ensure import ensure_callable, ensure_type

from .base import FT, VT
from .context import FieldContext
from .meta import FieldGroup


class LayoutFunction(Protocol[FT, VT]):
    """Layout given child views and return a new view."""

    def __call__(
        self,
        ctx: FieldContext[FT, VT],
        direction: Literal["row", "column"],
        child_views: list[VT],
    ) -> VT: ...


class LayoutManager(Generic[FT, VT]):
    """
    Generator for nested layout fields for a parent field of type "object".
    """

    def __init__(
        self,
        layout_function: LayoutFunction[FT, VT],
        property_views: dict[str, VT],
    ):
        ensure_callable("layout_function", layout_function)
        ensure_type("property_views", property_views, dict)
        self._layout_function = layout_function
        self._property_views = property_views

    def layout(self, ctx: FieldContext[FT, VT]) -> VT:
        """
        Generate a layout field for a value of type "object".
        """
        assert ctx.schema.type == DataType.object
        assert ctx.meta.layout is not None
        group: FieldGroup
        if ctx.meta.layout == "row":
            group = FieldGroup(type="row")
        elif ctx.meta.layout == "column":
            group = FieldGroup(type="column")
        else:
            assert isinstance(ctx.meta.layout, FieldGroup)
            group = ctx.meta.layout
        return self._layout_by_group(ctx, group, dict(self._property_views))

    def _layout_by_group(
        self,
        ctx: FieldContext[FT, VT],
        group: FieldGroup,
        property_views: dict[str, VT],
    ) -> VT:
        child_views: list[VT]
        if not group.items:
            child_views = list(property_views.values())
            property_views.clear()
        else:
            child_views = []
            for group_item in group.items:
                if isinstance(group_item, FieldGroup):
                    child_view = self._layout_by_group(ctx, group_item, property_views)
                else:
                    assert isinstance(group_item, str)
                    assert isinstance(ctx.meta.properties, dict)
                    prop_name: str = group_item
                    if prop_name not in property_views:
                        raise ValueError(
                            f"property {prop_name!r} not found in object "
                            f"field {ctx.meta.name!r}"
                        )
                    child_view = property_views[prop_name]
                    property_views.pop(prop_name)
                child_views.append(child_view)
        return self._layout_function(ctx, group.type, child_views)
