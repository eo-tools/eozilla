#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any, TypeAlias

from ..vm import ViewModel

View: TypeAlias = Any


class UIField(ABC):
    """
    Adapter that allows using a component or view from some UI component library
    together with a view model of type `ViewModel`.
    """

    @property
    @abstractmethod
    def view_model(self) -> ViewModel:
        """The view model used by this field."""

    @property
    @abstractmethod
    def view(self) -> View:
        """The view used by this field."""


class UIFieldBase(UIField, ABC):
    """Abstract base class for UI fields."""

    def __init__(self, view_model: ViewModel, view: View):
        self._view_model = view_model
        self._view = view
        self._bind()

    @property
    def view_model(self) -> ViewModel:
        return self._view_model

    @property
    def view(self) -> View:
        return self._view

    def _bind(self) -> None:
        """
        Bind view and view model, optionally mutually.
        Called from constructor.
        The default does nothing.
        """
