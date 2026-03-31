#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


"""A minimal mock UI component library."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, Literal, TypeVar

Observer = Callable[[], None]

T = TypeVar("T")

_DEFAULT_WIDTH = 20


class Rendering:
    """The result of rendering a view."""

    def __init__(self, lines: list[str]):
        self.lines = lines

    @property
    def width(self) -> int:
        """Get the width of the rendering."""
        width = 0
        for line in self.lines:
            width = max(width, len(line))
        return width

    @property
    def height(self) -> int:
        """Get the width of the rendering."""
        return len(self.lines)

    @classmethod
    def empty(cls) -> "Rendering":
        return Rendering([])

    def box(
        self,
        border: str | None = None,
        width: int | None = None,
        height: int | None = None,
        **_style,
    ) -> "Rendering":
        if height is not None:
            if height < self.height:
                lines = self.lines[:height]
            elif height > self.height:
                lines = self.lines + (height - self.height) * [""]
            else:
                lines = list(self.lines)
        else:
            lines = list(self.lines)

        target_width = self.width
        if width is not None and width < target_width:
            target_width = width

        lines = [_force_width(line, target_width) for line in lines]

        if border:
            lines = (
                [(2 + 2 + target_width) * "-"]
                + [f"| {line} |" for line in lines]
                + [(2 + 2 + target_width) * "-"]
            )

        return Rendering(lines)


# noinspection PyMethodMayBeStatic
class View(ABC):
    """Abstract base class for all Libui views."""

    def __init__(self, **props: Any):
        self.props = props
        self.observers: set[Observer] = set()

    @property
    def label(self) -> str | None:
        label = self.props.get("label") or None
        assert label is None or isinstance(label, str)
        return label

    @abstractmethod
    def render(self) -> Rendering:
        """Render the UI"""

    def watch(self, observer: Observer) -> None:
        self.observers.add(observer)

    def unwatch(self, observer: Observer) -> None:
        self.observers.discard(observer)

    def _notify(self) -> None:
        for observer in list(self.observers):
            observer()


class Container(View, ABC):
    """A container that arranges child views."""

    def __init__(self, *children: View | str | Literal[False] | None, **props) -> None:
        super().__init__(**props)
        self.children = [
            (c if isinstance(c, View) else Text(str(c)))
            for c in children
            if c is not None and c is not False
        ]


class Row(Container):
    """Container for views arranged in a row."""

    def render(self) -> Rendering:
        if not self.children:
            return Rendering.empty()
        renderings = [c.render() for c in self.children]
        target_height = 0
        for r in renderings:
            target_height = max(target_height, r.height)
        if target_height == 0:
            return Rendering.empty()
        boxes = [rendering.box(height=target_height) for rendering in renderings]
        lines: list[str] = []
        for y in range(target_height):
            lines.append(" ".join(box.lines[y] for box in boxes))
        return Rendering(lines).box(**self.props)


class Column(Container):
    """Container for views arranged in a column."""

    def render(self) -> Rendering:
        if not self.children:
            return Rendering.empty()
        renderings = [c.render() for c in self.children]
        target_width = 0
        for r in renderings:
            target_width = max(target_width, r.width)
        if target_width == 0:
            return Rendering.empty()
        boxes = [r.box(width=target_width) for r in renderings]
        lines: list[str] = []
        for box in boxes:
            lines.extend(box.lines)
        return Rendering(lines).box(**self.props)


class Widget(Generic[T], View, ABC):
    """Abstract base class for views that have a primary value."""

    def __init__(self, **props):
        super().__init__(**props)

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


class WidgetBase(Generic[T], Widget[T], ABC):
    """Abstract base class for views that have a primary value."""

    def __init__(self, value: T, **props):
        super().__init__(**props)
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

    def __init__(self, value: T | None, child: Widget[T], **props) -> None:
        super().__init__(value=value, **props)
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

    def render(self) -> Rendering:
        return Row(self.child_enabled_switch, self.child, **self.props).render()


class ListEditor(WidgetBase[list[Any]]):
    """An editor that can add/remove/change items of a value of type `list`."""

    def render(self) -> Rendering:
        label = self.label
        return Column(
            label,
            Column(*[str(v) for v in self.value], border="-"),
            Row(Button("+"), Button("-")),
            **self.props,
        ).render()


class TextArea(WidgetBase[str]):
    """A text area field."""

    def render(self) -> Rendering:
        return Rendering(self.value.split("\n")).box(**self.props)


class Text(WidgetBase[str]):
    """A piece of text."""

    def render(self) -> Rendering:
        return Rendering([self.value])


class Button(WidgetBase[str]):
    """A button."""

    def render(self) -> Rendering:
        return Rendering(["[" + self.value + "]"])


class Input(Generic[T], WidgetBase[T]):
    """A text input field."""

    def render(self) -> Rendering:
        label = self.label
        width: int = self.props.pop("width", _DEFAULT_WIDTH)
        input_text = _force_width(str(self.value), width, "_")
        return Column(label, input_text, **self.props).render()


class TextInput(Input[str]):
    """A text input field."""


class NumberInput(Input[int | float]):
    """A number input field."""


class Slider(WidgetBase[int | float]):
    """A slider that has values between a given min/max."""

    def __init__(
        self, value: T, minimum: T | None = None, maximum: T | None = None, **props
    ):
        super().__init__(value, **props)
        self.minimum: T = minimum if minimum is not None else 0
        self.maximum: T = maximum if maximum is not None else self.minimum + 1

    def render(self) -> Rendering:
        label = self.label
        width = self.props.pop("width", _DEFAULT_WIDTH)
        index = round(
            width * (self.value - self.minimum) / (self.maximum - self.minimum)
        )
        slider_text = (index * "-") + "()" + max(0, width - index - 2) * "-"
        return Column(label, slider_text, **self.props).render()


class Select(Generic[T], WidgetBase[T]):
    """A select (dropdown)."""

    def __init__(self, value: T, options: list[T], **props) -> None:
        super().__init__(value, **props)
        self.options = options

    def render(self) -> Rendering:
        knob = " |v|"
        label = self.label
        width = self.props.pop("width", _DEFAULT_WIDTH) - len(knob)
        select_text = _force_width(str(self.value), width)
        return Column(label, select_text).render()


class Checkbox(WidgetBase[bool]):
    """Checkbox field."""

    def toggle(self):
        self.value = not self.value

    def render(self) -> Rendering:
        label = self.label
        knob = "[x]" if self.value else "[ ]"
        return Rendering([f"{knob} {label}" if label else knob])


class Switch(WidgetBase[bool]):
    """A switch."""

    def toggle(self):
        self.value = not self.value

    def render(self) -> Rendering:
        label = self.label
        knob = "( |o)" if self.value else "(-| )"
        return Rendering([f"{knob} {label}" if label else knob])


def _force_width(text: str, width: int, fill: str = " ") -> str:
    text_length = len(text)
    if text_length < width:
        return text + fill * (width - text_length)
    if text_length > width:
        return text[:width]
    return text
