#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


"""A minimal mock UI component library."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, TypeVar

Observer = Callable[[], None]

T = TypeVar("T")


# noinspection PyMethodMayBeStatic
class View(Generic[T], ABC):
    """Abstract base class for all Libui views."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.observers: set[Observer] = set()

    @property
    def value(self) -> T:
        return self._get_value()

    @value.setter
    def value(self, value: T) -> None:
        self._set_value(value)

    @abstractmethod
    def _get_value(self) -> T:
        pass

    @abstractmethod
    def _set_value(self, value: T) -> None:
        pass

    def render(self):
        """Render the UI"""
        raise NotImplementedError

    def watch(self, observer: Observer) -> None:
        self.observers.add(observer)

    def unwatch(self, observer: Observer) -> None:
        self.observers.discard(observer)

    def _notify(self) -> None:
        for observer in list(self.observers):
            observer()


class Panel(View[dict[str, Any]]):
    """A panel that arranges named child views."""

    def __init__(self, children: dict[str, View], **kwargs) -> None:
        super().__init__(**kwargs)
        self.children = children

    def _get_value(self) -> dict[str, Any]:
        return {k: v.value for k, v in self.children.items()}

    def _set_value(self, value: dict[str, Any]) -> None:
        assert isinstance(value, dict)

        changed: bool = False

        def on_child_change():
            nonlocal changed
            changed = True

        try:
            for v in self.children.values():
                v.watch(on_child_change)
            for k, v in value.items():
                self.children[k].value = v
        finally:
            for v in self.children.values():
                v.unwatch(on_child_change)

        if changed:
            self._notify()


class Row(Panel):
    """Container for views arranged in a row."""


class Column(Panel):
    """Container for views arranged in a column."""


class NullableView(Generic[T], View[T | None]):
    """A view used to enable/disable another child view.
    If the child is enabled, this view's value is the value of the child view.
    Otherwise, the value of this view is `None`.
    """

    def __init__(self, value: T | None, child: View, **kwargs) -> None:
        super().__init__(value=value, **kwargs)
        self.child_enabled_switch = Switch(value=value is not None)
        self.child = child
        if value is not None:
            child.value = value
        self.child_enabled_switch.watch(self.on_switch_change)
        self.child.watch(self.on_child_change)

    def _get_value(self) -> T | None:
        if self.child_enabled_switch.value:
            return self.child.value
        else:
            return None

    def _set_value(self, value: T | None):
        if value is not None:
            self.child_enabled_switch.value = True
            self.child.value = value
        else:
            self.child_enabled_switch.value = False

    def on_switch_change(self):
        self._notify()

    def on_child_change(self):
        if self.child_enabled_switch.value:
            self._notify()


class Widget(Generic[T], View[T], ABC):
    """Abstract base class for views that have a primary value."""

    def __init__(self, *args, value: T, **kwargs):
        super().__init__(*args, **kwargs)
        self._value = value

    def _get_value(self) -> T:
        return self._value

    def _set_value(self, value: T) -> None:
        if value == self._value:
            return
        self._value = value
        self._notify()


class ListEditor(Widget[list[Any]]):
    """An editor that can add/remove/change items of a value of type `list`."""


class TextArea(Widget[str]):
    """A text area field."""


class TextInput(Widget[str]):
    """A text input field."""


class NumberInput(Widget[int | float]):
    """A number input field."""


class Slider(Widget[int | float]):
    """A slider that has values between a given min/max."""


class Checkbox(Widget[bool]):
    """Checkbox field."""

    def toggle(self):
        self.value = not self.value


class Switch(Widget[bool]):
    """A switch."""

    def toggle(self):
        self.value = not self.value


class Select(Generic[T], Widget[T]):
    """A select (dropdown)."""

    def __init__(self, *args, value: T, options: list[T], **kwargs) -> None:
        super().__init__(*args, value=value, **kwargs)
        self.options = options
