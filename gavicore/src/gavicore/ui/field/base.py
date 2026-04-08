#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from gavicore.ui.vm import ViewModel
from gavicore.util.ensure import ensure_type

VT = TypeVar("VT")
"""
A concrete piece of UI of typically data-bound UI 
(`view` such as widget, panel, control).
"""


class Field(ABC, Generic[VT]):
    """
    A binding unit between data, represented by property `view_model`,
    and a concrete piece of typically data-bound UI, represented by the
    `view` property of type `T`, such as a widget, panel, control.
    """

    @property
    @abstractmethod
    def view_model(self) -> ViewModel:
        """The view model used by this field."""

    @property
    @abstractmethod
    def view(self) -> VT:
        """The view used by this field."""


FT = TypeVar("FT", bound=Field)
"""
A field type for a specific view type.
"""


class FieldBase(Field[VT], ABC, Generic[VT]):
    """Abstract base class for UI fields."""

    def __init__(self, view_model: ViewModel, view: VT):
        ensure_type("view_model", view_model, ViewModel)
        self._view_model = view_model
        self._view = view
        self._bind()

    @property
    def view_model(self) -> ViewModel:
        return self._view_model

    @property
    def view(self) -> VT:
        return self._view

    def _bind(self) -> None:
        """
        Bind view and view model, optionally mutually.
        Called from this class' constructor.
        The default implementation does nothing.
        """
