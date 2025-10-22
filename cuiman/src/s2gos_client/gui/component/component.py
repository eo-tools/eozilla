#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable, Optional

import panel as pn
import param

from .json import (
    JsonCodec,
    JsonIdentityCodec,
    JsonValue,
)


class Component:
    def __init__(
        self,
        viewable: param.Parameterized,
        json_codec: Optional[JsonCodec] = None,
    ):
        super().__init__()
        self.viewable = viewable
        self.json_codec = JsonIdentityCodec() if json_codec is None else json_codec

    def get_json_value(self) -> Any:
        """Get the viewable's value as a json value."""
        return self.json_codec.to_json(self.get_value())

    def set_json_value(self, json_value: JsonValue):
        """Sets the viewable's value from a json value."""
        self.set_value(self.json_codec.from_json(json_value))

    def get_value(self) -> Any:
        """Get the viewable's value."""
        raise NotImplementedError

    def set_value(self, value: Any):
        """Sets the viewable's value."""
        raise NotImplementedError

    def watch_value(self, callback: Callable[[Any], Any]):
        """Watch for value changes in the viewable."""
        raise NotImplementedError


class WidgetComponent(Component):
    def __init__(self, widget: pn.widgets.Widget, json_codec: JsonCodec | None = None):
        super().__init__(widget, json_codec=json_codec)

    @property
    def widget(self) -> pn.widgets.Widget:
        # noinspection PyTypeChecker
        return self.viewable

    def get_value(self) -> Any:
        """Get the viewable's value."""
        return self.widget.value

    def set_value(self, value: Any):
        """Sets the viewable's value."""
        self.widget.value = value

    def watch_value(self, callback: Callable[[Any], Any]):
        """Watch for value changes in the viewable."""
        self.widget.param.watch(callback, "value")
