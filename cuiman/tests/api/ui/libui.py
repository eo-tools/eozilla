#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


"""A mock UI component library."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, TypeVar

Observer = Callable[[], None]

T = TypeVar("T")


# noinspection PyMethodMayBeStatic
class View(Generic[T], ABC):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.observers: list[Observer] = []

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
        return None

    def watch(self, observer: Observer) -> None:
        self.observers.append(observer)

    def unwatch(self, observer: Observer) -> None:
        self.observers.remove(observer)

    def notify(self) -> None:
        for observer in self.observers:
            observer()


class Panel(View[dict[str, Any]]):
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
            self.notify()


class Widget(Generic[T], View[T]):
    def __init__(self, *args, value: T, **kwargs):
        super().__init__(*args, **kwargs)
        self._value = value

    def _get_value(self) -> T:
        return self._value

    def _set_value(self, value: T) -> None:
        if value == self._value:
            return
        self._value = value
        self.notify()


class NullableView(Generic[T], View[T | None]):
    def __init__(self, value: T | None, view: View, **kwargs) -> None:
        super().__init__(value=value, **kwargs)
        self.checkbox = Checkbox(value=value is None)
        self.child_view = view
        if value is not None:
            view.value = value
        self.checkbox.watch(self.on_checkbox_change)
        self.child_view.watch(self.on_child_view_change)

    def _get_value(self) -> T | None:
        if self.checkbox.value:
            return None
        else:
            return self.child_view.value

    def _set_value(self, value: T | None):
        if value is None:
            self.checkbox.value = False
        else:
            self.checkbox.value = True
            self.child_view.value = value

    def on_checkbox_change(self):
        self.notify()

    def on_child_view_change(self):
        if self.checkbox.value:
            self.notify()


class ListEditor(Widget[list[Any]]):
    pass


class TextField(Widget[str]):
    pass


class IntegerField(Widget[int]):
    pass


class NumberField(Widget[int | float]):
    pass


class Slider(Widget[int | float]):
    pass


class Checkbox(Widget[bool]):
    pass


class Switch(Widget[bool]):
    pass
