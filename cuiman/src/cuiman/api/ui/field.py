#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .fieldmeta import UIFieldMeta
from .vm import ViewModel

VMT = TypeVar("VMT", bound=ViewModel)
VT = TypeVar("VT")


class UIField(Generic[VMT, VT], ABC):
    @abstractmethod
    def get_meta(self) -> UIFieldMeta:
        """Return the field metadata."""

    @abstractmethod
    def get_view_model(self) -> VMT:
        """Return the node use by this field."""

    @abstractmethod
    def get_view(self) -> VT:
        """Return the node use by this field."""


class UIFieldBase(Generic[VMT, VT], ABC):
    def __init__(self, meta: UIFieldMeta):
        self._meta = meta

    def get_meta(self) -> UIFieldMeta:
        return self._meta


class UIBuilderContext:
    def __init__(self, builder: "UIBuilder"):
        self._builder = builder

    @property
    def builder(self) -> "UIBuilder":
        return self._builder


class UIFieldFactory(Generic[VMT, VT], ABC):
    @abstractmethod
    def compute_field_score(
        self, ctx: UIBuilderContext, field_meta: UIFieldMeta
    ) -> int:
        """Compute the score of the given field metadata."""

    @abstractmethod
    def create_field(
        self, ctx: UIBuilderContext, field_meta: UIFieldMeta
    ) -> UIField[VMT, VT]:
        """Compute the score of the given field metadata."""


class UIBuilder:
    def __init__(self):
        self.factories = []

    def register_factory(self, factory: UIFieldFactory):
        self.factories.append(factory)

    def create_ui(self, field_meta: UIFieldMeta, path: list[str]) -> UIField:
        ctx = UIBuilderContext(self)

        max_score = 0
        best_factory: UIFieldFactory | None = None
        for f in self.factories:
            s = f.compute_field_score(ctx, field_meta)
            if s > max_score:
                max_score = s
                best_factory = f

        if best_factory is None:
            field_path = (".".join(path) + "." if path else "") + field_meta.name
            raise ValueError(f"Failed creating a UI field for field {field_path!r}")

        return best_factory.create_field(ctx, field_meta)
