#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


"""A minimal mock UI component library."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, TypeVar

Observer = Callable[[], None]

T = TypeVar("T")


class RenderResult:
    """The result of a rendering of a UIField."""

    def __init__(self, lines: list[str]):
        self.lines = lines


# noinspection PyMethodMayBeStatic
class View(ABC):
    """Abstract base class for all Libui views."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    @abstractmethod
    def render(self) -> RenderResult:
        """Render the UI"""


class Container(View, ABC):
    """A container that arranges child views."""

    def __init__(self, children: list[View], **kwargs) -> None:
        super().__init__(**kwargs)
        self.children = children


class Row(Container):
    """Container for views arranged in a row."""

    def render(self) -> RenderResult:
        return RenderResult([])


class Column(Container):
    """Container for views arranged in a column."""

    def render(self) -> RenderResult:
        return RenderResult([])


class Widget(Generic[T], View, ABC):
    """Abstract base class for views that have a primary value."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observers: set[Observer] = set()

    @property
    def value(self) -> T:
        return self._get_value()

    @value.setter
    def value(self, v: T) -> None:
        self._set_value(v)

    @abstractmethod
    def _get_value(self) -> T:
        """Get the current value."""

    @abstractmethod
    def _set_value(self, value: T) -> None:
        """Set a new value."""

    def watch(self, observer: Observer) -> None:
        self.observers.add(observer)

    def unwatch(self, observer: Observer) -> None:
        self.observers.discard(observer)

    def _notify(self) -> None:
        for observer in list(self.observers):
            observer()


class WidgetBase(Generic[T], Widget[T], ABC):
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


class NullableWidget(Generic[T], Widget[T | None]):
    """A view used to enable/disable another child view.
    If the child is enabled, this view's value is the value of the child view.
    Otherwise, the value of this view is `None`.
    """

    def __init__(self, value: T | None, child: Widget[T], **kwargs) -> None:
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

    def render(self) -> RenderResult:
        return RenderResult([])


class ListEditor(WidgetBase[list[Any]]):
    """An editor that can add/remove/change items of a value of type `list`."""

    def render(self) -> RenderResult:
        return RenderResult([])


class TextArea(WidgetBase[str]):
    """A text area field."""

    def render(self) -> RenderResult:
        return RenderResult([])


class TextInput(WidgetBase[str]):
    """A text input field."""

    def render(self) -> RenderResult:
        return RenderResult([])


class NumberInput(WidgetBase[int | float]):
    """A number input field."""

    def render(self) -> RenderResult:
        return RenderResult([])


class Slider(WidgetBase[int | float]):
    """A slider that has values between a given min/max."""

    def render(self) -> RenderResult:
        return RenderResult([])


class Checkbox(WidgetBase[bool]):
    """Checkbox field."""

    def toggle(self):
        self.value = not self.value

    def render(self) -> RenderResult:
        return RenderResult([])


class Switch(WidgetBase[bool]):
    """A switch."""

    def toggle(self):
        self.value = not self.value

    def render(self) -> RenderResult:
        return RenderResult([])


class Select(Generic[T], WidgetBase[T]):
    """A select (dropdown)."""

    def __init__(self, *args, value: T, options: list[T], **kwargs) -> None:
        super().__init__(*args, value=value, **kwargs)
        self.options = options

    def render(self) -> RenderResult:
        return RenderResult([])
